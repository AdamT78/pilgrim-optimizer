#!/usr/bin/env python3
"""Drag the nine duty tiles against the acolyte grid, and save where they land.

    python3 ui/render/gen_tile_offsets.py --serve     # drag and Save writes the file
    python3 ui/render/gen_tile_offsets.py --open      # same page, read-only, prints the JSON

WHY THIS EXISTS WHEN gen_layout_tool.py SAYS IT SHOULD NOT

That file states the rule plainly: "Nothing drags, nothing can be repositioned. Where things go
lives in the generators, where a coordinate can carry the paragraph that explains it; a drag handle
throws that reasoning away." It then says why it is allowed to hold that line -- "none of the open
questions here are 'where should this sit', they are 'how big, and does it still fit'".

This question IS "where should this sit", and three attempts at a derivable rule have failed:

    ink centroid vs row centre   predicted the opposite of what the eye wanted on Allocation
    mean base depth per tile     all nine already within 1.1 px of each other; nothing to fix
    per-figure local edge depth  equalises the burial exactly and makes the row visibly ragged,
                                 because the eye wants a level row far more than equal depth

So the number is a judgement, and the honest place for a judgement is a file that says it is one.
The rule's real point still binds: the coordinate must carry its reasoning. So the file this writes
carries `note` and `method` alongside the numbers, and they are not decoration -- without them a
later reader finds nine magic pairs and no way to tell whether they were measured or guessed.

WHAT MOVES AND WHAT DOES NOT

The acolyte grid is computed once, from the tiles at their unoffset positions, and then frozen. It
does not move. This is the whole mechanism: an earlier attempt derived each row from its own tile's
bounding box, so moving a tile moved its row with it and the relationship was invariant -- the
tiles visibly shuffled and the fit did not change at all.

Tiles move against the frozen grid. Offsets are in SCREEN PIXELS at the board's real drawn size
(877.8 px for the whole wheel), not grid units, because that is what the eye is judging in.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
sys.path.insert(0, str(HERE))

import gen_duty_grid as dg  # noqa: E402

OFFSETS_PATH = UI / "duty_tile_offsets.json"
WHEEL_PX = 877.8                    # the wheel's real drawn size in the game view
TILE_K = 0.92                       # tiles scaled about their centres, to open the channel
SAMPLE = [[2, 1, 0, 3], [1, 0, 0, 0], [0, 2, 1, 0], [3, 0, 2, 1], [0, 0, 0, 0],
          [1, 1, 1, 1], [2, 0, 0, 0], [0, 1, 0, 2], [1, 0, 3, 0]]

NOTE = ("Per-tile nudges so each tile sits on its acolyte row the way The City does. Judged by "
        "eye: see gen_tile_offsets.py for the three derivable rules that were tried and why each "
        "failed. Screen pixels at the wheel's real drawn size, positive = right / down.")


def load_offsets() -> dict[int, tuple[float, float]]:
    if not OFFSETS_PATH.is_file():
        return {}
    data = json.loads(OFFSETS_PATH.read_text(encoding="utf-8"))
    out = {}
    for k, v in (data.get("offsets") or {}).items():
        if k.isdigit() and 0 <= int(k) < 9:
            out[int(k)] = (float(v.get("dx", 0)), float(v.get("dy", 0)))
    return out


def decompose(offsets: dict) -> dict:
    """What the nine numbers ARE, as arithmetic rather than as opinion.

    This exists because the prose describing this file went stale twice, and both times it went
    stale in the same expensive way: it kept describing an earlier set of numbers, so a reader --
    me, twice -- reasoned about offsets that no longer existed.

    What it reports is the part a human should not have to re-derive: how much of the nine is a
    plain column effect, a plain row effect, or a single uniform push. THAT is the diagnostic.
    Structure here means something mechanical is being closed by hand and belongs in a constant
    instead. It is not hypothetical -- the first set of these was almost entirely one contraction,
    because `tile_scale` shrank each tile about its own centre and let every gap grow. Naming that
    is what moved it into MARGIN, which is where a spread belongs, and the offsets that survived
    were a third the size.

    Arithmetic only. Whether a given structure is worth moving is a judgement, and judgements go
    in `what_they_turned_out_to_be`, next to the numbers they were formed about.
    """
    saved = [offsets.get(i, offsets.get(str(i), {"dx": 0.0, "dy": 0.0}))
             for i in range(9)]
    dx = [float(o["dx"]) for o in saved]
    dy = [float(o["dy"]) for o in saved]
    colm = [sum(dx[3 * r + c] for r in range(3)) / 3 for c in range(3)]
    rowm = [sum(dy[3 * r + c] for c in range(3)) / 3 for r in range(3)]
    res = []
    for i in range(9):
        r, c = divmod(i, 3)
        res.append(((dx[i] - colm[c]) ** 2 + (dy[i] - rowm[r]) ** 2) ** 0.5)

    # dy against each tile's distance below the wheel centre: a uniform push plus a stretch
    box = dg.load()["box"]
    k = WHEEL_PX / box
    u = []
    for d in dg.laid_shapes(offsets=False):
        P = _pts(d)
        u.append((sum(p[1] for p in P) / len(P) - box / 2.0) * k)
    n = len(u)
    mu, mv = sum(u) / n, sum(dy) / n
    sxx = sum((x - mu) ** 2 for x in u)
    b = sum((u[i] - mu) * (dy[i] - mv) for i in range(n)) / sxx if sxx else 0.0
    a = mv - b * mu
    err = sum(abs(dy[i] - (a + b * u[i])) for i in range(n)) / n

    return {
        "_": "computed by gen_tile_offsets.decompose on every save; do not edit by hand",
        "dx_mean_by_column": [round(v, 1) for v in colm],
        "dy_mean_by_row": [round(v, 1) for v in rowm],
        "left_after_removing_rows_and_columns_px": {"mean": round(sum(res) / 9, 1),
                                                    "worst": round(max(res), 1)},
        "dy_as_uniform_push_plus_stretch": {
            "uniform_px": round(a, 1),
            "per_px_below_wheel_centre": round(b, 4),
            "mean_error_px": round(err, 1),
        },
        "read_this_as": ("A strong column signal in dx or row signal in dy, or a large uniform_px "
                         "with a small mean_error_px, means these are not nine judgements: "
                         "something mechanical is being done nine times by hand and belongs in a "
                         "layout constant. MARGIN was raised from 14 to 33 for exactly that."),
    }


def load_shift(path: pathlib.Path = OFFSETS_PATH) -> tuple[float, float]:
    """Where the whole nine sits in the box, in screen px. Not one of the per-tile nudges."""
    if not path.is_file():
        return 0.0, 0.0
    d = (json.loads(path.read_text(encoding="utf-8")).get("arrangement_shift") or {})
    return float(d.get("dx", 0.0)), float(d.get("dy", 0.0))


def margins_at_zero() -> dict:
    """The four margins, in screen px, with the arrangement shift taken back out.

    Computed here rather than measured in the browser because a shift is a rigid translation:
    every margin moves by exactly it, so the page can add the shift itself and be exact. Reading
    them back off the DOM would mean trusting getBoundingClientRect through a clip-path, which is
    not reliably the rendered bounds.
    """
    box = dg.load()["box"]
    k = WHEEL_PX / box
    sx, sy = load_shift()
    laid = dg.laid_shapes(offsets=True)
    xs, ys = [], []
    for d in laid:
        P = _pts(d)
        xs += [q[0] for q in P]
        ys += [q[1] for q in P]
    grid = acolyte_grid(dg.laid_shapes(offsets=False))
    foot = max(g["sy"] + g["fh"] for g in grid)
    return {
        "l": min(xs) * k - sx, "r": (box - max(xs)) * k + sx,
        "t": min(ys) * k - sy, "b": (box - max(ys)) * k + sy,
        "foot": (box - foot) * k + sy,          # clearance below the lowest acolyte
    }


def save_offsets(offsets: dict, note: str = NOTE, shift: tuple | None = None) -> None:
    """Write the file, keeping everything in it this function does not own.

    TWO THINGS THIS GOT WRONG, both of which only a save could show.

    `wheel_px` was not written at all. gen_duty_grid reads it to turn screen pixels into grid units
    and falls back to treating them as grid units when it is missing -- so the first Save silently
    made every offset 14% too small, which reads as a slightly clumsy drag rather than as a unit
    error. It is written explicitly now.

    And the body was rebuilt from scratch every time, so a Save dropped any field added to the file
    by hand. That took out the paragraphs recording what the offsets turned out to be -- the exact
    provenance this file exists to carry, deleted by the act of using the tool. Anything already in
    the file and not owned here is preserved.
    """
    existing = {}
    if OFFSETS_PATH.is_file():
        try:
            existing = json.loads(OFFSETS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    owned = {
        "note": note,
        "method": "dragged in ui/render/gen_tile_offsets.py against a frozen acolyte grid",
        "units": "screen px at wheel width %g; positive = right / down" % WHEEL_PX,
        "wheel_px": WHEEL_PX,
        "tile_scale": TILE_K,
        "names": dg.DUTY_NAMES,
        "offsets": {str(i): {"dx": round(float(v["dx"]), 1), "dy": round(float(v["dy"]), 1)}
                    for i, v in sorted(offsets.items(), key=lambda kv: int(kv[0]))},
        # Where the whole block sits, kept apart from the nine on purpose: it moves the acolyte
        # rows with the tiles, and they move nothing relative to each other.
        "arrangement_shift": {"dx": round(float((shift or load_shift())[0]), 1),
                              "dy": round(float((shift or load_shift())[1]), 1)},
    }
    # Recorded rather than raised: a save that dies here would cost a drag, and a save that
    # silently dropped it is the exact fault this file already had once.
    try:
        owned["measured"] = decompose(offsets)
    except Exception as exc:                                   # noqa: BLE001
        owned["measured"] = {"error": "decompose() failed: %s" % exc}
    # the caller's own notes first, then what this function owns, then anything else it was keeping
    body = {k: v for k, v in existing.items() if k not in owned}
    body.update(owned)
    OFFSETS_PATH.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def _pts(d):
    n = [float(v) for v in d.replace("M", " ").replace("Z", " ").replace("L", " ").split()]
    return [(n[i], n[i + 1]) for i in range(0, len(n), 2)]


def scaled_shapes():
    """The tiles as the BOARD lays them out, unoffset. dg.laid_shapes does the work.

    This used to scale the raw traced shapes here and skip `dg.place`, which re-lays the nine as an
    even 3x3 and spreads them apart. The tool therefore showed a TIGHTER arrangement than the board
    builds -- up to 25.6 screen px per tile, measured when MARGIN was 14 -- so offsets dragged in it
    were judged against tiles that were never where the board would put them. They then applied
    exactly, to two decimals, and the board still looked wrong, which is the hardest kind of wrong
    to find: nothing is broken anywhere, the two halves simply disagree about the question.

    Asking the grid where its tiles are, rather than working it out again, is the only thing that
    keeps this true the next time `place` or the tile scale changes.
    """
    return dg.laid_shapes(offsets=False)


def acolyte_grid(shapes):
    """Computed once from the unoffset tiles, then frozen. Nothing here moves again.

    `dg.acolyte_box` does the arithmetic. This file used to repeat it, along with FIG_FRAC, the
    overlap and the aspect -- a second copy of the geometry the board actually draws, in the one
    tool whose whole job is to judge tiles against it. Asking the grid is what keeps the rows this
    page freezes identical to the rows the board emits.

    FOUR SEATS, always, whatever a real game has. The row is drawn for the players at the table,
    so two players get two figures -- but the row stays CENTRED on its tile at every count, so a
    tile placed correctly against four is placed correctly against two. Four is simply the widest
    case, and the widest is the one worth judging a placement against.
    """
    return [dg.acolyte_box(d) for d in shapes]


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Duty tile offsets</title><style>
*{box-sizing:border-box}
html,body{margin:0;height:100%%;background:#15130f;color:#d8d2c0;
  font:14px "Iowan Old Style",Georgia,serif}
#wrap{display:flex;height:100%%}
#stage{flex:1;position:relative;overflow:hidden;
  background:#0b0a08 url(%(ground)s) center/100%% 100%% no-repeat}
#wheel{position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%);
  width:%(px).1fpx;height:%(px).1fpx}
#wheel svg{width:100%%;height:100%%;display:block}
/* THE REFERENCE RECTANGLE. #gv-wheel on the real board is exactly this square -- 877.8 px, flush
   with its column left and right, with the banner's bottom edge sitting ON its top edge. So these
   four lines are the edges the rest of the board actually meets, and the margins in the panel are
   measured from them. Without it the stage is an unbounded dark field and a margin has nothing to
   be a margin FROM.
   pointer-events:none on both, because this is a drag tool and an overlay that eats the pointer
   would be a strange way to break it. */
#boxline,#guide{position:absolute;inset:0;pointer-events:none}
#boxline{border:1px solid rgba(214,58,48,.85)}
#guide{border:1px dashed rgba(214,58,48,.55)}
#wheel.nomarks #boxline,#wheel.nomarks #guide{display:none}
.dgt{cursor:grab}
.dgt.sel{cursor:grabbing}
/* The wheel's real hover lighting is live in here because the component is lifted whole, and in a
   PLACEMENT tool it is a liability: the tile under the pointer -- always the one being moved --
   lights gold, and you cannot judge where a thing sits while it is glowing. Off for this page
   only; nothing about the component changes. */
#wheel .dg-lit{opacity:0!important}
#wheel .dgt:has(.dg-hit:hover) .dg-edge{stroke:#2b2114!important;stroke-opacity:.85!important}
/* Selection is a dashed halo rather than a gold edge, because gold is what hover already means. */
.dgt.sel .dg-edge{stroke:#e8d8a0!important;stroke-opacity:1!important;stroke-width:3.4!important;
  stroke-dasharray:9 6}
#side{width:330px;flex:none;padding:14px 16px;background:#1d1a15;overflow:auto;
  border-left:1px solid #332d24}
h1{font-size:15px;margin:0 0 4px}
h2{font-size:12px;margin:16px 0 4px;color:#8d8672;font-weight:normal;
  text-transform:uppercase;letter-spacing:.08em}
#marg td{font-variant-numeric:tabular-nums}
#marg td.k{text-align:left;color:#cfc7b0}
#marg tr.eq td{color:#9fc49a}
p.hint{font-size:12px;color:#9a937f;line-height:1.5;margin:0 0 12px}
table{border-collapse:collapse;width:100%%;font:12px ui-monospace,Menlo,monospace}
td,th{padding:3px 6px;text-align:right;border-bottom:1px solid #2b261e}
th{color:#8d8672;font-weight:normal;text-align:right}
td.n{text-align:left;color:#cfc7b0}
tr.sel td{background:#2c2719;color:#f0e6c8}
button{font:13px Georgia,serif;background:#2b3128;color:#cfc9b6;border:1px solid #4b5342;
  border-radius:5px;padding:5px 11px;cursor:pointer;margin:10px 6px 0 0}
button:hover{background:#39422f}
#msg{font-size:12px;color:#9fc49a;min-height:34px;margin-top:8px;line-height:1.45}
textarea{width:100%%;height:150px;margin-top:8px;background:#121510;color:#c6d2ba;
  border:1px solid #333b2c;font:11px ui-monospace,Menlo,monospace}
</style></head><body>
<div id="wrap">
  <div id="stage"><div id="wheel">%(svg)s
    <div id="boxline"></div><div id="guide"></div></div></div>
  <div id="side">
    <h1>Duty tile offsets</h1>
    <p class="hint">Drag a tile, or click it and use the arrow keys &mdash; 1&nbsp;px, or
    10&nbsp;px with Shift. The acolyte row never moves; only the tiles do.
    Offsets are screen pixels at this size.</p>
    <table id="tbl"><tr><th class="n" style="text-align:left">tile</th><th>dx</th><th>dy</th></tr>
    </table>
    <h2>Whole arrangement</h2>
    <p class="hint">Hold <b>Alt</b> with the arrow keys to move all nine <i>and</i> their acolyte
    rows together &mdash; nothing moves relative to anything else. Shift for 10&nbsp;px.<br>
    The solid red line is the wheel&rsquo;s real box on the board: the banner sits on its top edge
    and the column meets it left and right. The dashed line is the left margin carried round all
    four sides &mdash; bring the top row down to it and top equals left.</p>
    <table id="marg"></table>
    <button id="toplft">Top = Left</button><button id="unshift">Zero the shift</button>
    <button id="marks">Hide the red box</button>
    <h2>Saving</h2>
    <button id="save">Save</button><button id="reset">Reset all</button>
    <button id="zero">Zero selected</button>
    <div id="msg">%(msg)s</div>
    <textarea id="json" readonly></textarea>
  </div>
</div>
<script>
var NAMES = %(names)s, CAN_SAVE = %(can_save)s, K = %(k).6f;
var off = %(offsets)s;                       // {i: {dx, dy}} in screen px
var shift = %(shift)s;                       // where all nine sit, in screen px
var BASE = %(base)s;                         // the four margins with the shift taken out
var sel = null;

function tiles(){ return Array.prototype.slice.call(
    document.querySelectorAll('#wheel g.dgt')); }

function margins(){
  // a shift is a rigid translation, so every margin moves by exactly it
  return {l: BASE.l + shift.dx, r: BASE.r - shift.dx,
          t: BASE.t + shift.dy, b: BASE.b - shift.dy, foot: BASE.foot - shift.dy};
}

function apply(){
  tiles().forEach(function(g,i){
    var o = off[i] || {dx:0,dy:0};
    // screen px -> grid units, because the svg's own coordinates are the viewBox's
    g.setAttribute('transform','translate('+((o.dx+shift.dx)/K).toFixed(3)+','
                                           +((o.dy+shift.dy)/K).toFixed(3)+')');
  });
  // the acolyte rows take the shift and NOTHING else: that is what keeps them still against the
  // tiles while the block moves. A per-tile nudge must never reach them.
  var ac = document.getElementById('acol');
  if (ac) { ac.setAttribute('transform','translate('+(shift.dx/K).toFixed(3)+','
                                                    +(shift.dy/K).toFixed(3)+')'); }
  var m = margins(), eq = Math.abs(m.t - m.l) < 0.05;
  // the dashed inset sits at the LEFT margin on all four sides, so "match the top to the left"
  // is a thing you can see the top row meet rather than a number to chase
  var gEl = document.getElementById('guide');
  if (gEl) { gEl.style.inset = m.l.toFixed(2) + 'px'; }
  document.getElementById('marg').innerHTML =
      '<tr><td class="k">shift</td><td>' + (shift.dx>0?'+':'') + shift.dx.toFixed(1)
    + '</td><td>' + (shift.dy>0?'+':'') + shift.dy.toFixed(1) + '</td></tr>'
    + '<tr class="' + (eq?'eq':'') + '"><td class="k">top / left</td><td>' + m.t.toFixed(1)
    + '</td><td>' + m.l.toFixed(1) + '</td></tr>'
    + '<tr><td class="k">bottom / right</td><td>' + m.b.toFixed(1)
    + '</td><td>' + m.r.toFixed(1) + '</td></tr>'
    + '<tr><td class="k">below acolytes</td><td colspan="2">' + m.foot.toFixed(1) + '</td></tr>';
  var rows = ['<tr><th class="n" style="text-align:left">tile</th><th>dx</th><th>dy</th></tr>'];
  NAMES.forEach(function(n,i){
    var o = off[i] || {dx:0,dy:0};
    rows.push('<tr class="'+(sel===i?'sel':'')+'" data-i="'+i+'"><td class="n">'+n+'</td><td>'
      + (o.dx>0?'+':'') + o.dx.toFixed(1) + '</td><td>' + (o.dy>0?'+':'') + o.dy.toFixed(1)
      + '</td></tr>');
  });
  document.getElementById('tbl').innerHTML = rows.join('');
  Array.prototype.forEach.call(document.querySelectorAll('#tbl tr[data-i]'), function(tr){
    tr.onclick = function(){ pick(+tr.dataset.i); };
  });
  document.getElementById('json').value = JSON.stringify(off, null, 2);
}

function pick(i){
  sel = i;
  tiles().forEach(function(g,j){ g.classList.toggle('sel', j===i); });
  apply();
}

var drag = null;
tiles().forEach(function(g,i){
  g.addEventListener('pointerdown', function(e){
    e.preventDefault(); pick(i);
    var o = off[i] || {dx:0,dy:0};
    drag = {i:i, x:e.clientX, y:e.clientY, dx:o.dx, dy:o.dy};
    g.setPointerCapture(e.pointerId);
  });
  g.addEventListener('pointermove', function(e){
    if (!drag || drag.i !== i) return;
    // the stage is drawn at its true size, so a client pixel IS a board pixel
    off[i] = {dx: drag.dx + (e.clientX-drag.x), dy: drag.dy + (e.clientY-drag.y)};
    apply();
  });
  g.addEventListener('pointerup', function(){ drag = null; });
});

addEventListener('keydown', function(e){
  var dd = {ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];
  if (dd && e.altKey) {                      // the whole block, rows included
    e.preventDefault();
    var st = e.shiftKey ? 10 : 1;
    shift = {dx: shift.dx + dd[0]*st, dy: shift.dy + dd[1]*st};
    apply();
    return;
  }
  if (sel === null) return;
  var d = dd;
  if (!d) return;
  e.preventDefault();
  var step = e.shiftKey ? 10 : 1;
  var o = off[sel] || {dx:0,dy:0};
  off[sel] = {dx: o.dx + d[0]*step, dy: o.dy + d[1]*step};
  apply();
});

document.getElementById('toplft').onclick = function(){
  // top margin == left margin, solved rather than nudged toward
  shift = {dx: shift.dx, dy: shift.dy + (BASE.l + shift.dx) - (BASE.t + shift.dy)};
  apply();
  document.getElementById('msg').textContent =
      'Top margin set equal to the left. Not saved yet.'; };
document.getElementById('unshift').onclick = function(){ shift = {dx:0,dy:0}; apply(); };
document.getElementById('marks').onclick = function(){
  var w = document.getElementById('wheel'), off = w.classList.toggle('nomarks');
  this.textContent = off ? 'Show the red box' : 'Hide the red box'; };
document.getElementById('reset').onclick = function(){ off = {}; apply();
  document.getElementById('msg').textContent = 'All offsets cleared. Not saved yet.'; };
document.getElementById('zero').onclick = function(){
  if (sel !== null) { delete off[sel]; apply(); } };

document.getElementById('save').onclick = function(){
  var msg = document.getElementById('msg');
  if (!CAN_SAVE) {
    msg.textContent = 'Not served, so nothing can be written. Run with --serve, or copy the '
                    + 'JSON below into ui/duty_tile_offsets.json.';
    return;
  }
  fetch('/offsets', {method:'PUT', headers:{'Content-Type':'application/json'},
                     body: JSON.stringify({offsets: off, shift: shift})})
    .then(function(r){
      if (r.ok) { msg.textContent = 'Saved to ui/duty_tile_offsets.json.'; return; }
      // the reason matters far more than the number: a 409 means this tab is out of date
      return r.text().then(function(t){
        // BaseHTTPRequestHandler.send_error puts its explanation in `<p>Message: ...</p>`
        var m = /<p>Message:\\s*([^<]*)/.exec(t);
        msg.textContent = 'Refused (' + r.status + '). '
          + ((m && m[1]) ? m[1].trim() : 'Check the terminal running the tool.');
      });
    })
    .catch(function(err){ msg.textContent = 'Could not reach the server: ' + err; });
};

apply();
</script></body></html>
"""


def build(can_save: bool) -> str:
    shapes = scaled_shapes()
    # `offsets=False`, and NOT meta=<already-laid shapes>. Passing pre-laid shapes back in made
    # duty_grid_svg lay them out and offset them a second time, and the page's own JS then applied
    # the file a third: the tool opened 27.1 px per tile away from what the board draws. It is the
    # grid's job to lay the tiles out; the only thing this page wants is for it to stop short of
    # the offsets, which it moves itself.
    svg = dg.duty_grid_svg(labels=dg.DUTY_NAMES, version=dg.VERSION,
                           klass="wheel", arrows=False, offsets=False)
    # `dg.acolyte_row` DRAWS these, and this file no longer draws anything of its own.
    #
    # It used to emit its own figures -- its own copy of the duotone builder, its own seat palette,
    # its own numeral -- and that was survivable only while both drew the same picture. The moment
    # the board started piling figures upward, a tool still drawing one figure per seat would have
    # shown a row the board does not draw, and every offset judged in it would have been judged
    # against the wrong thing. That exact fault has already happened here twice: once with `place`,
    # once with the row geometry, and both times the numbers applied perfectly and the result
    # still looked wrong. The arithmetic was merged into `dg.acolyte_box` then; the drawing is
    # merged now, and there is nothing left in this file for the two to disagree about.
    marks = [dg.acolyte_row(shapes[i], SAMPLE[i]) for i in range(len(shapes))]
    # The acolytes go in AFTER the tiles and outside every tile group, which is what freezes them:
    # a drag transforms one `g.dgt` and cannot reach anything here.
    # one group, so the page can translate the rows with the tiles by the arrangement shift
    svg = svg.replace("</svg>", '<g id="acol">' + "".join(marks) + "</g></svg>")

    saved = load_offsets()
    msg = ("Loaded %d offset%s from ui/duty_tile_offsets.json."
           % (len(saved), "" if len(saved) == 1 else "s")) if saved else \
          "No ui/duty_tile_offsets.json yet; everything starts at zero."
    if not can_save:
        msg += " Read-only: run with --serve to enable Save."
    return PAGE % {
        "ground": dg.ground_uri(),
        "svg": svg,
        "px": WHEEL_PX,
        "k": WHEEL_PX / dg.load()["box"],
        "names": json.dumps(dg.DUTY_NAMES),
        "can_save": "true" if can_save else "false",
        "offsets": json.dumps({str(i): {"dx": dx, "dy": dy} for i, (dx, dy) in saved.items()}),
        "shift": json.dumps({"dx": load_shift()[0], "dy": load_shift()[1]}),
        "base": json.dumps({k: round(v, 2) for k, v in margins_at_zero().items()}),
        "msg": msg,
    }


SELF = pathlib.Path(__file__).resolve()


def _sources() -> list[pathlib.Path]:
    """The Python this page is built from -- the only inputs read once instead of per request."""
    return [SELF, pathlib.Path(dg.__file__).resolve()]


def _stamp() -> dict[str, int]:
    return {str(p): p.stat().st_mtime_ns for p in _sources() if p.is_file()}


STALE_PAGE = """<!doctype html><meta charset="utf-8"><title>Restart the tool</title>
<style>body{margin:0;display:flex;align-items:center;justify-content:center;height:100vh;
background:#2a1512;color:#f0ddd4;font:16px/1.6 Georgia,serif}
div{max-width:44em;padding:28px 34px;background:#3a1d18;border:1px solid #6b332a;border-radius:8px}
h1{font-size:19px;margin:0 0 10px}code{background:#20100d;padding:2px 6px;border-radius:3px;
font:14px ui-monospace,Menlo,monospace}p{margin:0 0 12px}</style>
<div><h1>%s changed on disk. This server is running the old code.</h1>
<p>Python is read once, when the process starts. Rebuilding the page per request re-reads the
offsets and the traced shapes, but it cannot re-read this. Anything served from here now would be
built from code that no longer exists in the tree &mdash; which is exactly the failure that had
this tool opening on tile positions nobody saved.</p>
<p>Stop it with Ctrl-C and start it again:</p>
<p><code>python3 ui/render/gen_tile_offsets.py --serve --open</code></p>
<p>Nothing was lost. Your offsets are in <code>ui/duty_tile_offsets.json</code> and the restarted
tool seeds from them.</p></div>
"""


def serve(port: int):
    """A local server so Save can write, rebuilding the page on every request.

    WHAT "REBUILT PER REQUEST" DOES AND DOES NOT BUY, because this docstring used to claim the
    whole thing and deliver half of it.

    Rebuilding re-reads `duty_tile_offsets.json` and `duty_grid_shapes.json`, because `build` and
    `dg.load` open them every call. It does NOT re-read a single line of Python: `import
    gen_duty_grid` ran once, at startup, and `build` calls into that module object forever after.

    So a server left running across an edit serves a page that looks freshly built and is built
    from code that has been replaced -- under a rebuild-per-request docstring promising the
    opposite. It cost three rounds of "the tiles are not where I saved them", the last one after
    the bug it was blamed on had already been fixed and measured at 0.001 px.

    Now the sources are stamped at startup and checked on every request. `gen_duty_grid` is a real
    imported module and simply gets reloaded. This file cannot reload itself -- run as a script it
    has no spec for `importlib.reload` -- so it refuses to serve instead, which is the point: a
    placement tool that quietly shows the wrong placement is worse than one that stops.
    """
    import http.server
    import importlib

    start = _stamp()

    def refresh() -> str | None:
        """Reload what can be reloaded; name the file that forces a restart, if any."""
        now = _stamp()
        if now.get(str(SELF)) != start.get(str(SELF)):
            return SELF.name
        dgp = str(pathlib.Path(dg.__file__).resolve())
        if now.get(dgp) != start.get(dgp):
            importlib.reload(dg)
            start[dgp] = now[dgp]
            print("reloaded %s (it changed on disk)" % pathlib.Path(dgp).name)
        return None

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            stale = refresh()
            if stale:
                body = (STALE_PAGE % stale).encode("utf-8")
                self.send_response(409)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.end_headers()
                self.wfile.write(body)
                return
            try:
                body = build(can_save=True).encode("utf-8")
            except Exception as exc:                       # noqa: BLE001
                body = ("<pre>gen_tile_offsets.py did not build:\n\n%s\n\nFix it and reload.</pre>"
                        % exc).encode("utf-8")
                self.send_response(500)
            else:
                self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.end_headers()
            self.wfile.write(body)

        def do_PUT(self):
            if not self.path.startswith("/offsets"):
                self.send_error(404)
                return
            # A tab rendered before the edit is still live and can still Save. Its tiles are where
            # the old code put them, so its numbers are judgements about geometry that no longer
            # exists -- the one thing that must never reach the file.
            stale = refresh()
            if stale:
                self.send_error(409, "%s changed on disk; restart the tool and re-drag. Refusing "
                                     "to save numbers judged against the old layout." % stale)
                return
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                self.send_error(400, str(exc))
                return
            # {offsets: {...}, shift: {...}}, or a bare {...} of offsets from an older page.
            # The bare form is still accepted because a tab open across a restart will send it,
            # and losing a drag to a payload rename would be a silly way to lose one.
            body = data.get("offsets") if isinstance(data.get("offsets"), dict) else data
            raw_shift = data.get("shift") if isinstance(data, dict) else None
            clean = {}
            for k, v in body.items():
                if not (str(k).isdigit() and 0 <= int(k) < 9):
                    self.send_error(400, "tile index out of range: %r" % (k,))
                    return
                clean[int(k)] = {"dx": float(v.get("dx", 0)), "dy": float(v.get("dy", 0))}
            shift = None
            if isinstance(raw_shift, dict):
                try:
                    shift = (float(raw_shift.get("dx", 0)), float(raw_shift.get("dy", 0)))
                except (TypeError, ValueError):
                    self.send_error(400, "arrangement shift is not a pair of numbers: %r"
                                    % (raw_shift,))
                    return
                if max(abs(shift[0]), abs(shift[1])) > WHEEL_PX / 2:
                    self.send_error(400, "arrangement shift of %r would move the wheel off its "
                                         "own box" % (shift,))
                    return
            save_offsets(clean, shift=shift)
            print("saved %s  (%d tiles, shift %s)"
                  % (OFFSETS_PATH, len(clean), shift if shift else "unchanged"))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_a):
            pass

    try:
        server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        if exc.errno not in (48, 98):
            raise
        print("port %d is taken, almost certainly by a copy of this tool left running.\n"
              "  stop it with:  lsof -ti tcp:%d | xargs kill\n"
              "Starting on a free port instead." % (port, port))
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    return server, "http://127.0.0.1:%d/" % server.server_port


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--serve", action="store_true", help="run a local server so Save can write")
    ap.add_argument("--port", type=int, default=8767)
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--output", default=None)
    z = ap.parse_args()

    if z.serve:
        server, url = serve(z.port)
        print("serving %s\n  Save writes %s\n  Ctrl-C to stop" % (url, OFFSETS_PATH))
        if z.open:
            import webbrowser
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
        return

    out = pathlib.Path(z.output) if z.output else UI / "generated" / "duty-tile-offsets.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(can_save=False), encoding="utf-8")
    print("written %s  (%.1f MB)" % (out, out.stat().st_size / 1024 / 1024))
    print("  read-only: drag works, Save does not. Run with --serve to write %s"
          % OFFSETS_PATH.name)
    if z.open:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
