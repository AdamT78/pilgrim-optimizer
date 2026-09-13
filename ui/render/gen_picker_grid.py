#!/usr/bin/env python3
"""A picker for the 3x3 duty grid: the board with art in, and one picture in all nine shapes.

    python3 ui/render/gen_picker_grid.py --tiles ui/assets-gothic/duty-tiles --open

TWO QUESTIONS, TWO VIEWS

*Board* answers "does this work at the size it is actually drawn". The grid sits in the wheel's own
slot at the layout's own scale, so a tile is ~245 canvas units and an action half ~123. Everything
that has disappointed so far disappointed at that size and looked fine at four times it.

*Shapes* answers a question that is easy to miss: the nine outlines are NOT interchangeable. They
were traced from a generated sheet, so each is its own shape, and putting the same picture through
all nine shows what each one does to it. Measured on the traced paths:

    aspect      0.966 .. 1.130          the top row is 15% squatter than the rest
    inside all nine                     70.6% of the frame
    common safe box                     x 4.5%..95.5%, y 5.2%..94.5%

So square art loses more top and bottom in the top row than elsewhere, and anything that must
survive has to sit inside about a 5% margin -- which is where the 6% rule in the art spec came
from, now confirmed against the shapes rather than assumed.

The subtler one is where a two-action tile's join lands. The art puts it at 50% of the PICTURE, but
what reads as centred is 50% of the SHAPE's ink, and those differ:

    tile 0   46.5% of the shape lies left of the midline
    tile 2   52.2%
    the rest 49.2% .. 50.6%

Tile 0 is Allocation, which has no join, so only tile 2 (Construct) is affected, by 2.2% -- about
five pixels at a 245 unit tile. Worth knowing before assigning art to positions, and fixable the
same way an off-centre join already is: move the gradient.

MISSING TILES ARE A STATE, NOT AN ERROR

Art is still being generated. A tile with no picture draws its flat region colour, so the page is
useful from the first tile onwards and shows at a glance which are still outstanding.
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
import sys
sys.path.insert(0, str(HERE))
from gen_duty_grid import DUTY_NAMES, TILE_FILLS, INK, TWO_ACTION, load  # noqa: E402
try:                                        # the tool's own screen list, so the two agree
    from gen_layout_tool import SCREENS
except Exception:                           # importing it runs no work, but do not depend on it
    SCREENS = [("this window, true size", 0, 0, 0),
               ("ultrawide 3440x1440", 3440, 1300, 109.7),
               ("1440p 2560x1440", 2560, 1300, 108.8),
               ("1080p laptop 15.6in", 1920, 940, 141.2),
               ('14" MacBook', 1512, 860, 127.0)]

SLUGS = ["allocation", "clerical", "construct", "build_roads", "city",
         "ordination", "produce", "taxation", "give_alms"]
# The shapes view labels each cell by WHERE it is, not by which duty lives there. The duty name
# would describe the shape while the picture in it is whichever the dropdown chose -- a caption
# contradicting the thing it sits under. Position is also the useful unit when deciding which
# art to move where.
POSITIONS = ["top left", "top centre", "top right",
             "middle left", "centre", "middle right",
             "bottom left", "bottom centre", "bottom right"]
DIM = ('<feColorMatrix type="saturate" values="0.40"/><feComponentTransfer>'
       '<feFuncR type="linear" slope=".94" intercept=".005"/>'
       '<feFuncG type="linear" slope=".96" intercept=".010"/>'
       '<feFuncB type="linear" slope="1.02" intercept=".025"/></feComponentTransfer>')
LIT = ('<feColorMatrix type="saturate" values="1.20"/><feComponentTransfer>'
       '<feFuncR type="linear" slope="1.34" intercept=".10"/>'
       '<feFuncG type="linear" slope="1.14" intercept=".055"/>'
       '<feFuncB type="linear" slope=".78" intercept="0"/></feComponentTransfer>')


def find_tiles(root: pathlib.Path | None, version: str) -> dict[int, pathlib.Path]:
    """`NN_slug_V.png` anywhere under root. Absent tiles are simply absent."""
    if not root or not root.is_dir():
        return {}
    found = {}
    pat = re.compile(r"^(\d{2})_([a-z_]+)_([AB])\.(png|webp|jpg)$", re.I)
    for p in sorted(root.rglob("*")):
        m = pat.match(p.name)
        if m and m.group(3).upper() == version.upper():
            i = int(m.group(1)) - 1
            if 0 <= i < 9:
                found[i] = p
    return found


def embed(p: pathlib.Path, px: int = 760, quality: int = 82) -> str:
    """One data URI per picture, re-encoded for a preview page.

    The source tiles are 1254 px PNGs of dense engraving -- 3.5 MB each. A picker that inlines
    them raw, once per place they are drawn, reaches 71 MB for two tiles; that was the first
    version of this file. Downscaled to the size the page actually draws and encoded as WebP,
    the same tile is about 60 KB.
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


def bbox(path_d: str):
    n = [float(v) for v in path_d.replace("M", " ").replace("Z", " ").replace("L", " ").split()]
    xs, ys = n[0::2], n[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def sprite_svg(tiles):
    """Every available picture, embedded once, as <symbol>s both views reference.

    A <symbol> rather than an <image> because width/height on <use> resize a symbol and are
    ignored on an image -- and the two views draw the same picture at different sizes. Cross-<svg>
    <use> by fragment id is the ordinary SVG sprite technique, so this can live once at the top
    of the page instead of once per view.
    """
    out = ['<svg id="sprite" aria-hidden="true" style="position:absolute;width:0;height:0">'
           '<defs>']
    for v, byver in sorted(tiles.items()):
        for i, href in sorted(byver.items()):
            out.append(f'<symbol id="src{v}{i}" viewBox="0 0 100 100" '
                       f'preserveAspectRatio="xMidYMid slice">'
                       f'<image href="{href}" width="100" height="100" '
                       f'preserveAspectRatio="xMidYMid slice"/></symbol>')
    out.append("</defs></svg>")
    return "".join(out)


def grid_svg(meta, tiles, joins, version, klass="wheel"):
    """The grid, each shape clipping its own picture, hover lighting one half."""
    box = meta["box"]
    parch = "#%02x%02x%02x" % tuple(meta.get("parchment", (245, 195, 120)))
    out = [f'<svg class="{klass} board-v" data-v="{version}" viewBox="0 0 {box} {box}" '
           f'xmlns="http://www.w3.org/2000/svg">'
           f'<defs><filter id="pg-dim-{version}" color-interpolation-filters="sRGB">{DIM}</filter>'
           f'<filter id="pg-lit-{version}" color-interpolation-filters="sRGB">{LIT}</filter>'
           f'<filter id="pg-glow-{version}" x="-8%" y="-8%" width="116%" height="116%">'
           f'<feMorphology in="SourceAlpha" operator="dilate" radius="{box*0.004:.1f}" result="f"/>'
           f'<feFlood flood-color="#d8b23a" flood-opacity=".95"/>'
           f'<feComposite in2="f" operator="in" result="r"/>'
           f'<feMerge><feMergeNode in="r"/><feMergeNode in="SourceGraphic"/></feMerge></filter>']

    for i, d in enumerate(meta["shapes"]):
        x0, y0, x1, y1 = bbox(d)
        out.append(f'<clipPath id="pg-c{version}{i}"><path d="{d}"/></clipPath>')
        if i in tiles:
            out.append(f'<g id="pg-img{version}{i}"><use href="#src{version}{i}" '
                       f'x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}"/></g>')
            j = joins.get(i, 0.5)
            # gradient across the SHAPE's own box, centred on the art's measured join
            out.append(
                f'<linearGradient id="pg-gr{version}{i}" x1="{x0}" x2="{x1}" '
                f'gradientUnits="userSpaceOnUse">'
                f'<stop offset="{max(0.0, j-0.09):.3f}" stop-color="#000"/>'
                f'<stop offset="{min(1.0, j+0.09):.3f}" stop-color="#fff"/></linearGradient>'
                f'<mask id="pg-mR{version}{i}" maskUnits="userSpaceOnUse" x="{x0}" y="{y0}" '
                f'width="{x1-x0}" height="{y1-y0}">'
                f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" '
                f'fill="url(#pg-gr{version}{i})"/></mask>'
                f'<mask id="pg-mL{version}{i}" maskUnits="userSpaceOnUse" x="{x0}" y="{y0}" '
                f'width="{x1-x0}" height="{y1-y0}">'
                f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="#fff"/>'
                f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" '
                f'fill="url(#pg-gr{version}{i})" style="mix-blend-mode:difference"/></mask>')
    out.append("</defs>")
    out.append(f'<rect width="{box}" height="{box}" fill="{parch}"/>')

    for i, d in enumerate(meta["shapes"]):
        x0, y0, x1, y1 = bbox(d)
        w, h = x1 - x0, y1 - y0
        name = DUTY_NAMES[i]
        out.append(f'<g data-duty-tile="{i}" data-duty-name="{name}" class="pgt">')
        if i in tiles:
            img = '<use href="#pg-img%s%d"/>' % (version, i)
            body = [f'<g clip-path="url(#pg-c{version}{i})">']
            if i == 4:                       # the city is never dimmed
                body.append(img)
            else:
                body.append(f'<g filter="url(#pg-dim-{version})">{img}</g>')
                for side in (("L", "R") if i in TWO_ACTION else ("F",)):
                    m = f' mask="url(#pg-m{side}{version}{i})"' if side != "F" else ""
                    body.append(f'<g class="pg-lit pg-lit-{side}"{m}>'
                                f'<g filter="url(#pg-lit-{version})">{img}</g></g>')
            body.append("</g>")
            out.append("".join(body))
        else:
            out.append(f'<path d="{d}" fill="{TILE_FILLS[i]}" opacity="0.85"/>'
                       f'<text x="{(x0+x1)/2:.0f}" y="{(y0+y1)/2:.0f}" text-anchor="middle" '
                       f'font-family="Georgia,serif" font-size="{box*0.018:.0f}" '
                       f'fill="#2b2114" opacity=".55">no art</text>')
        out.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-opacity=".85" '
                   f'stroke-width="{box*0.0035:.2f}" stroke-linejoin="round" '
                   f'class="pg-edge"/>')
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)


def shapes_view(meta, tiles, first):
    """The same picture through all nine outlines, with which picture as a live control.

    Choosing it at build time was the wrong shape for a picker: the whole question is how a given
    picture fares in each shape, and comparing two pictures meant regenerating the page. The nine
    cells are <use> elements and the control repoints them.
    """
    box = meta["box"]
    COL, GAP = 300, 16
    boxes = [bbox(d) for d in meta["shapes"]]
    scale = COL / max(x1 - x0 for x0, _, x1, _ in boxes)
    rows_h = [max((boxes[r * 3 + c][3] - boxes[r * 3 + c][1]) for c in range(3)) * scale
              for r in range(3)]
    W = 3 * COL + 2 * GAP
    H = sum(rows_h) + 2 * GAP + 3 * 34

    out = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" xmlns="http://www.w3.org/2000/svg" '
           f'class="shapes-svg"><defs>']
    for i, d in enumerate(meta["shapes"]):
        x0, y0, x1, y1 = boxes[i]
        out.append(f'<clipPath id="sv-c{i}"><path d="{d}" '
                   f'transform="translate({-x0:.1f},{-y0:.1f})"/></clipPath>')
    out.append("</defs>")

    y = 0.0
    for i, d in enumerate(meta["shapes"]):
        r, c = divmod(i, 3)
        if c == 0 and i:
            y += rows_h[r - 1] + GAP + 34
        x0, y0, x1, y1 = boxes[i]
        w, h = (x1 - x0) * scale, (y1 - y0) * scale
        out.append(f'<g transform="translate({c * (COL + GAP):.1f},{y:.1f})">'
                   f'<rect width="{w:.1f}" height="{h:.1f}" fill="#151810"/>'
                   f'<g transform="scale({scale:.4f})" clip-path="url(#sv-c{i})">')
        if first is not None:
            out.append(f'<use class="sv-pic" href="#src{first}" '
                       f'width="{x1-x0:.0f}" height="{y1-y0:.0f}"/>')
        else:
            out.append(f'<rect width="{x1-x0:.0f}" height="{y1-y0:.0f}" fill="{TILE_FILLS[i]}"/>')
        out.append(f'</g><path d="{d}" transform="scale({scale:.4f}) '
                   f'translate({-x0:.1f},{-y0:.1f})" fill="none" stroke="{INK}" '
                   f'stroke-opacity=".8" stroke-width="{box * 0.0035 / scale:.1f}"/>'
                   f'<text x="0" y="{h+15:.0f}" font-family="Georgia,serif" font-size="13" '
                   f'fill="#a9b09b">{POSITIONS[i]}</text>'
                   f'<text x="0" y="{h+30:.0f}" font-family="Georgia,serif" font-size="11" '
                   f'fill="#767d69">{x1-x0:.0f} &#215; {y1-y0:.0f} &#183; '
                   f'aspect {(x1-x0)/(y1-y0):.3f}</text></g>')
    out.append("</svg>")
    return "".join(out)


PAGE = """<!doctype html><meta charset="utf-8"><title>Duty grid picker</title>
<style>
html,body{margin:0;background:#20241c;color:#d8d2c0;font:14px Georgia,serif}
header{padding:14px 20px;border-bottom:1px solid #3b4133;display:flex;gap:18px;align-items:baseline}
h1{font-size:16px;margin:0;font-weight:normal;letter-spacing:.04em}
nav button{font:13px Georgia,serif;background:#2b3128;color:#cfc9b6;border:1px solid #4b5342;
  padding:5px 14px;cursor:pointer}
nav button.on{background:#c9a227;color:#20241c;border-color:#c9a227}
.pick{margin:0 0 16px}
.pick label{color:#8d9581;font-size:12px;margin-right:6px}
.pick select{font:13px Georgia,serif;background:#2b3128;color:#cfc9b6;border:1px solid #4b5342;
  padding:4px 8px}
.pick .note{margin-left:12px}
.pick .ck{margin-left:14px;color:#8d9581;font-size:12px}
.pick .ck input{vertical-align:-1px;margin-right:4px}
header .hl{color:#8d9581;font-size:12px}
header select{font:13px Georgia,serif;background:#2b3128;color:#cfc9b6;
  border:1px solid #4b5342;padding:4px 8px}
.note{color:#8d9581;font-size:12px}
main{padding:20px}
section{display:none} section.on{display:block}
#board-wrap{width:%(slot)spx;max-width:100%%;background:#151810;padding:0;margin:0 auto}
#board-wrap svg{width:100%%;height:auto}
/* Both version boards live in the page; the control shows one. These need the #board-wrap
   prefix: an id selector beats a bare class, so `.board-v{display:none}` lost to
   `#board-wrap svg{display:block}` and both boards stayed visible. */
#board-wrap .board-v{display:none}
#board-wrap .board-v.on{display:block}
#shapes-wrap{width:980px;max-width:100%%}
#shapes-wrap .shapes-svg{display:block;width:100%%;height:auto}
figcaption{font-size:12px;color:#a9b09b;padding-top:5px}
figcaption span{color:#767d69;font-size:11px}
.pgt .pg-lit{opacity:0}
.pgt:hover .pg-lit-F{opacity:1}
.pgt:hover .pg-edge{stroke:#d8b23a;stroke-opacity:1}
.half-l:hover .pg-lit-L{opacity:1}
.half-r:hover .pg-lit-R{opacity:1}
table{border-collapse:collapse;font:12px ui-monospace,Menlo,monospace;margin-top:16px}
td,th{padding:3px 12px 3px 0;text-align:left;color:#a9b09b}
th{color:#767d69;font-weight:normal}
</style>
<header><h1>Duty grid</h1>
<nav><button id="t-board" class="on">board</button><button id="t-shapes">shapes</button></nav>
<nav id="vers"><button data-v="A" class="on">A engraved</button>
<button data-v="B">B grim dark</button></nav>
<label for="screen" class="hl">screen</label> <select id="screen">%(screens)s</select>
<span class="note" id="note">%(note)s</span></header>
%(sprite)s
<main>
<section id="s-board" class="on">
<p class="pick"><label for="fit" class="ck"><input type="checkbox" id="fit" checked>
fit to window</label><span class="note" id="size"></span></p>
<div id="board-wrap">%(grids)s</div>
<p class="note">Hover a tile. Two-action tiles light the half under the cursor; the city never
dims.</p></section>
<section id="s-shapes">
<p class="pick"><label for="sv-pick">picture</label> <select id="sv-pick">%(options)s</select>
<label for="sv-fit" class="ck"><input type="checkbox" id="sv-fit" checked>
fit to window</label><span class="note" id="sv-size"></span></p>
<div id="shapes-wrap">%(shapes)s</div>%(table)s</section>
</main>
<script>
const show = k => {
  for (const n of ['board','shapes']) {
    document.getElementById('s'+'-'+n).classList.toggle('on', n===k);
    document.getElementById('t'+'-'+n).classList.toggle('on', n===k);
  }
};
document.getElementById('t-board').onclick = () => { show('board'); fitAll(); };
document.getElementById('t-shapes').onclick = () => { show('shapes'); fitAll(); };
// Version is a control, not a build flag: both boards are in the page and only the markup is
// duplicated -- the pictures live once in the sprite, so switching costs nothing.
const NAMES = %(names)s, HAVE = %(have)s, NOTES = %(notes)s, SCREENS = %(screenlist)s;

// The board is a square in a page with a header and a caption. Left at a fixed width it is
// taller than the window and the page scrolls -- which is exactly the thing you cannot judge a
// layout through. So it is sized from whichever of width or height runs out first, the same
// rule gen_layout_tool uses, and the screen list is imported from there so the two agree.
// Both panes size the same way: from whichever of width or height runs out first. The board
// is square; the shapes grid is whatever its viewBox says. One screen picker drives both, so
// they cannot disagree about what screen is being simulated.
function avail(wrapId) {
  // Everything in the pane that is NOT the thing being sized -- control row, caption, and in the
  // shapes pane a nine-row table -- is MEASURED rather than allowed for with a constant. A
  // constant was 150, the table is about 200, and the shapes pane scrolled at every window size.
  const [name, sw, sh] = SCREENS[+document.getElementById('screen').value];
  const sec = document.querySelector('section.on');
  const wrap = document.getElementById(wrapId);
  const head = document.querySelector('header').getBoundingClientRect().height;
  const other = wrap ? sec.getBoundingClientRect().height - wrap.getBoundingClientRect().height
                     : 0;
  return {name: sw ? name : '', w: sw || sec.clientWidth,
          h: (sh || window.innerHeight) - head - other - 56};
}
function trueTile() {
  // what a tile really is on the chosen screen: the wheel slot is 787.8 canvas units of a
  // 1600 canvas, and a tile is 246.6 of those.
  const [, sw, sh] = SCREENS[+document.getElementById('screen').value];
  const vw = sw || window.innerWidth, vh = sh || window.innerHeight;
  return 246.6 * Math.min(vw / 1600, vh / 1200);
}
function fitBoard() {
  const wrap = document.getElementById('board-wrap');
  if (!wrap) return;
  const a = avail('board-wrap'), fit = document.getElementById('fit').checked;
  const side = fit ? Math.max(240, Math.min(a.w, a.h)) : 900;
  wrap.style.width = side.toFixed(0) + 'px';
  document.getElementById('size').textContent =
    (a.name ? a.name + ' \u2014 ' : '') + 'board ' + side.toFixed(0)
    + ' px \u00b7 tile ' + (side * 0.2456).toFixed(0)
    + ' \u00b7 half ' + (side * 0.1228).toFixed(0);
}
function fitShapes() {
  const wrap = document.getElementById('shapes-wrap');
  const svg = wrap && wrap.querySelector('svg');
  if (!svg) return;
  const vb = svg.getAttribute('viewBox').split(/\s+/).map(Number);
  const a = avail('shapes-wrap'), fit = document.getElementById('sv-fit').checked;
  const w = fit ? Math.max(300, Math.min(a.w, a.h * vb[2] / vb[3])) : 980;
  wrap.style.width = w.toFixed(0) + 'px';
  const cell = w * 300 / vb[2];             // a cell is 300 units of the grid's own viewBox
  document.getElementById('sv-size').textContent =
    (a.name ? a.name + ' \u2014 ' : '') + 'cell ' + cell.toFixed(0)
    + ' px \u00b7 a real tile is ' + trueTile().toFixed(0);
}
function fitAll() { fitBoard(); fitShapes(); }
document.getElementById('screen').onchange = fitAll;
document.getElementById('fit').onchange = fitBoard;
document.getElementById('sv-fit').onchange = fitShapes;
addEventListener('resize', fitAll);
let VER = 'A';
function setVersion(v) {
  VER = v;
  for (const b of document.querySelectorAll('#vers button'))
    b.classList.toggle('on', b.dataset.v === v);
  for (const g of document.querySelectorAll('.board-v'))
    g.classList.toggle('on', g.dataset.v === v);
  document.getElementById('note').textContent = NOTES[v];
  const sel = document.getElementById('sv-pick');
  const was = sel.value;
  sel.innerHTML = (HAVE[v] || []).length
    ? (HAVE[v].map(i => `<option value="${i}">${i} \u00b7 ${NAMES[i]}</option>`).join(''))
    : '<option>no art yet</option>';
  if ((HAVE[v] || []).includes(+was)) sel.value = was;
  sel.onchange();
}
for (const b of document.querySelectorAll('#vers button'))
  b.onclick = () => setVersion(b.dataset.v);
const pick = document.getElementById('sv-pick');
if (pick) pick.onchange = () => {
  // repoint all nine cells at the chosen picture. They are <use> elements sharing one sprite,
  // so this costs no new bytes -- which is the point of embedding each picture once.
  for (const u of document.querySelectorAll('.sv-pic')) {
    if (!/^\d+$/.test(pick.value)) { u.removeAttribute('href'); continue; }
    u.setAttribute('href', '#src' + VER + pick.value);
  }
};
// Hovering a two-action tile lights the half the cursor is on. The split is the tile's own
// measured join, not the middle of its box -- those differ by up to 2%% on the traced shapes.
for (const g of document.querySelectorAll('[data-duty-tile]')) {
  g.addEventListener('mousemove', e => {
    const b = g.getBoundingClientRect();
    const left = (e.clientX - b.left) / b.width < (parseFloat(g.dataset.join) || 0.5);
    g.classList.toggle('half-l', left);
    g.classList.toggle('half-r', !left);
  });
  g.addEventListener('mouseleave', () => g.classList.remove('half-l','half-r'));
}
setVersion('A');
fitAll();
</script>
"""


def main():
    ap = argparse.ArgumentParser(description="Preview the 3x3 duty grid, with art if there is any.")
    ap.add_argument("--tiles", default=None,
                    help="directory of NN_slug_V.png tiles; missing ones draw as flat colour")
    ap.add_argument("--joins", default=None,
                    help="json of joins; defaults to joins.json in the tiles directory")
    ap.add_argument("--output", default=None)
    ap.add_argument("--open", action="store_true")
    z = ap.parse_args()

    meta = load()
    root = pathlib.Path(z.tiles) if z.tiles else None
    # Both versions are loaded and both boards are built. Version is a control in the page, so
    # comparing A against B no longer means regenerating -- the same reason --sample went.
    tiles = {v: {i: embed(p) for i, p in find_tiles(root, v).items()} for v in ("A", "B")}

    jp = pathlib.Path(z.joins) if z.joins else (root / "joins.json" if root else None)
    book = json.loads(jp.read_text()) if jp and jp.is_file() else {}
    if book and all(k.isdigit() for k in book):        # a flat file from before versions
        book = {"A": book}
    joins = {v: {int(k): float(x) for k, x in book.get(v, {}).items()} for v in ("A", "B")}
    if jp and jp.is_file() and not z.joins:
        print("joins from %s" % jp)

    rows = ["<tr><th>tile</th><th>w</th><th>h</th><th>aspect</th>"
            "<th>join A</th><th>join B</th></tr>"]
    for i, d in enumerate(meta["shapes"]):
        x0, y0, x1, y1 = bbox(d)
        ja, jb = joins["A"].get(i), joins["B"].get(i)
        rows.append(f"<tr><td>{i} {DUTY_NAMES[i]}</td><td>{x1-x0:.0f}</td><td>{y1-y0:.0f}</td>"
                    f"<td>{(x1-x0)/(y1-y0):.3f}</td>"
                    f"<td>{'%.1f%%' % (ja*100) if ja else '&mdash;'}</td>"
                    f"<td>{'%.1f%%' % (jb*100) if jb else '&mdash;'}</td></tr>")

    have = {v: sorted(tiles[v]) for v in ("A", "B")}
    notes = {v: (f"{len(tiles[v])} of 9 tiles have art" if root else "no --tiles given: shapes only")
             for v in ("A", "B")}
    first = min(tiles["A"]) if tiles["A"] else (min(tiles["B"]) if tiles["B"] else None)
    options = "".join(f'<option value="{i}">{i} &#183; {DUTY_NAMES[i]}</option>'
                      for i in have["A"]) or '<option>no art yet</option>'

    html = PAGE % dict(
        slot=900,
        grids="".join(grid_svg(meta, tiles[v], joins[v], v) for v in ("A", "B")),
        sprite=sprite_svg(tiles),
        shapes=shapes_view(meta, tiles["A"], first),
        options=options,
        names=json.dumps(DUTY_NAMES), have=json.dumps(have), notes=json.dumps(notes),
        screens="".join(f'<option value="{i}">{n}</option>'
                        for i, (n, *_rest) in enumerate(SCREENS)),
        screenlist=json.dumps(SCREENS),
        table="<table>" + "".join(rows) + "</table>", note=notes["A"])
    for v in ("A", "B"):
        for i, j in joins[v].items():
            html = html.replace(f'<g data-duty-tile="{i}" data-duty-name',
                                f'<g data-join="{j}" data-duty-tile="{i}" data-duty-name', 1)

    out = pathlib.Path(z.output) if z.output else UI / "generated" / "duty-grid-picker.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print("written %s  (%.1f MB)" % (out, out.stat().st_size / 1024 / 1024))
    for v in ("A", "B"):
        print(f"  version {v}: {len(tiles[v])} of 9")
    if z.open:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
