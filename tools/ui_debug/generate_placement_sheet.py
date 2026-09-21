"""Every arrangement the placement rules produce, on one page, from the file that decides them.

    python3 tools/ui_debug/generate_placement_sheet.py --open

WHAT THIS IS FOR

`ui/assets-gothic/metadata/duty_placement.json` decides how acolyte sculpts stand on a duty
tile. Its numbers are small and abstract -- a spread, a set-back, a rank gap, all bare
pixels with no figure beside them -- and there is
no way to tell from reading them whether 2+1+1 will look deliberate or like a pile-up. This page
draws every case the rules will actually meet, so the file can be judged by its output rather
than by its values.

Change a number in the file, run this, look. That is the whole loop.

IT READS THE FILE, AND YOU CAN PROVE IT

The run prints the settings it used for every size. To check they came from the file rather than
from anywhere else, put an unmistakable value in it -- 999 -- and see it on the page. A tool
that claims to read a file is worth exactly as much as your ability to falsify the claim.

WHY ORDERED CASES, NOT SHAPES

Elsewhere in this toolchain the fifteen distinct SHAPES matter -- 2+1+1 counted once, whoever
owns the pair. Not here. This page is about what a seat's own sculpts look like, so `p1 p1 p2`
and `p2 p2 p1` are two different pictures and both are drawn. The seat colours are the point.

THE RULES ARE NOT COPIED HERE

`placement()` and `figures()` are imported from generate_duty_board_check.py, which owns them.
A second copy of the validator would drift from the first the day someone widens a range, and
both pages would then disagree about what a valid file is while each looked entirely correct.
"""

import argparse
import base64
import html
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated" / "placement_sheet.html"


def _board_module():
    """generate_duty_board_check.py, imported for the two functions it owns.

    Loaded by path rather than by name because it is a script rather than a package module, and
    because importing it must not depend on the caller's working directory.
    """
    sys.path.insert(0, str(ROOT / "ui" / "render"))
    spec = importlib.util.spec_from_file_location(
        "generate_duty_board_check", HERE / "generate_duty_board_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The cases, as counts per seat. Ordered rather than collapsed: whose sculpts they are changes
# the picture, because `grouped` sorts by seat and the colours sit where the sort puts them.
CASES = [
    ("one acolyte, p1",        (1, 0, 0)),
    ("one acolyte, p2",        (0, 1, 0)),
    ("one acolyte, p3",        (0, 0, 1)),
    ("one each, two seats",    (1, 1, 0)),
    ("one each, three seats",  (1, 1, 1)),
    ("a pair, one seat",       (2, 0, 0)),
    ("2 + 1",                  (2, 1, 0)),
    ("1 + 2",                  (1, 2, 0)),
    ("2 + 1 + 1",              (2, 1, 1)),
    ("1 + 2 + 1",              (1, 2, 1)),
    ("1 + 1 + 2",              (1, 1, 2)),
    ("2 + 2",                  (2, 2, 0)),
    ("three, one seat",        (3, 0, 0)),
    ("3 + 1",                  (3, 1, 0)),
    ("3 + 1 + 1",              (3, 1, 1)),
    ("2 + 2 + 1",              (2, 2, 1)),
    ("3 + 2",                  (3, 2, 0)),
    ("four, one seat",         (4, 0, 0)),
    ("4 + 1",                  (4, 1, 0)),
    ("five, one seat",         (5, 0, 0)),
]

GROUND = "#17130d"

# THE DRAWING RULES LIVE IN ONE FILE -- formation, seat order and the depth cue -- inlined
# into every page that draws acolytes. The formation was written out three times and the depth
# cue twice; they agreed only because they had been copied from each other.
RULES_JS = HERE / "duty_sculpt_rules.js"

def save_settings(board, sent):
    """Write the tuned numbers back into the placement file.

    MERGED, NOT OVERWRITTEN. The file carries more prose than numbers -- why the set is one set,
    what each control costs, what was measured -- and a save that replaced the document would
    throw all of it away the first time someone nudged a slider.

    Validated before it touches the disk, with the same rules the generator reads by, so the
    button cannot write a file the tool would then refuse to load.
    """
    current = json.loads(board.PLACEMENT.read_text(encoding="utf-8"))
    merged = dict(current)
    for key in ("spread", "back", "rank"):
        if key not in sent:
            raise ValueError("no %s in what the page sent" % key)
        value = sent[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("%s is %r, want a non-negative whole number" % (key, value))
        merged[key] = value
    if sent.get("order") not in ("grouped", "arrival"):
        raise ValueError("order is %r, want grouped or arrival" % sent.get("order"))
    merged["order"] = sent["order"]
    depth = sent.get("depth") or {}
    if depth.get("mode") not in ("haze", "dark", "off"):
        raise ValueError("depth.mode is %r, want haze, dark or off" % depth.get("mode"))
    if isinstance(depth.get("amount"), bool) or not isinstance(depth.get("amount"), int) \
            or not 0 <= depth["amount"] <= 100:
        raise ValueError("depth.amount is %r, want a whole number 0-100" % depth.get("amount"))
    if isinstance(depth.get("full_at"), bool) or not isinstance(depth.get("full_at"), int) \
            or depth["full_at"] <= 0:
        raise ValueError("depth.full_at is %r, want a positive whole number" % depth.get("full_at"))
    merged["depth"] = {"mode": depth["mode"], "amount": depth["amount"],
                       "full_at": depth["full_at"]}

    # Written via a neighbour and renamed into place: a crash halfway through a direct write
    # leaves the file truncated, and this one is read by every page in the toolchain.
    tmp = board.PLACEMENT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    tmp.replace(board.PLACEMENT)
    return merged


def serve(page, board, port, open_it):
    """Serve the page on localhost and accept its saves.

    Bound to 127.0.0.1 and nothing else. This writes a file in the repository when asked, which
    is fine for a tool you started yourself on your own machine and would not be fine on any
    interface a neighbour can reach.
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

        def do_GET(self):                                           # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):                                          # noqa: N802
            if self.path != "/save":
                return self._send(404, json.dumps({"error": "not found"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                sent = json.loads(self.rfile.read(n).decode("utf-8"))
                saved = save_settings(board, sent)
            except Exception as exc:                                # noqa: BLE001
                print("  refused a save: %s" % exc)
                return self._send(400, json.dumps({"error": str(exc)}))
            print("  saved  spread %d  set-back %d  rank %d  order %s  depth %s %d%%"
                  % (saved["spread"], saved["back"], saved["rank"], saved["order"],
                     saved["depth"]["mode"], saved["depth"]["amount"]))
            return self._send(200, json.dumps({"ok": True,
                                               "file": str(board._short(board.PLACEMENT))}))

        def log_message(self, *a):                                  # quiet; we print what matters
            return

    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    print("  serving %s -- the save button writes %s"
          % (url, board._short(board.PLACEMENT)))
    print("  ctrl-c to stop")
    board.show(url, open_it)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="where to write the page (default: %s)" % OUT.relative_to(ROOT))
    ap.add_argument("--figures", default=None, help="folder holding the rendered sculpts")
    ap.add_argument("--open", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--no-open", dest="open", action="store_false",
                    help="write the page without opening it")
    ap.add_argument("--serve", nargs="?", type=int, const=8765, default=None, metavar="PORT",
                    help="serve the page on localhost so its save button can write the file "
                         "(default port %(const)s); without this the button can only download")
    args = ap.parse_args()

    board = _board_module()
    out = pathlib.Path(args.out).expanduser() if args.out else OUT
    fig_dir = (pathlib.Path(args.figures).expanduser() if args.figures else board.FIGURE_DIR)

    notes = []
    place = board.placement(notes)
    figs = board.figures(fig_dir, notes)
    if not figs:
        raise SystemExit("no sculpt art -- run tools/ui_debug/make_tray_figures.py first; "
                         "this page is nothing but arrangements of it")

    sizes = sorted(int(k) for k in figs)   # figures() keys by string; work in ints
    orders = ["grouped", "arrival"]
    font = ""
    ffile = ROOT / "ui" / "assets" / "fonts" / "PirataOne-Regular.ttf"
    if ffile.is_file():
        font = "data:font/ttf;base64," + base64.b64encode(ffile.read_bytes()).decode("ascii")

    # The CASES and the art are data; the arrangement is computed in the page, because the
    # sliders change it while you watch. The rule doing that computing is the shared file.
    cases = [{"label": label, "counts": list(counts),
              "tag": "+".join(str(c) for c in counts if c) or "0"}
             for label, counts in CASES]
    if not RULES_JS.is_file():
        raise SystemExit("%s is missing -- it is where the drawing rules live"
                         % board._short(RULES_JS))

    art_uris = {str(px): [{"uri": f["uri"], "w": f["w"], "h": f["h"]}
                          for f in figs[str(px)]] for px in sizes}
    page = TEMPLATE
    for key, val in (("__FONT__", font), ("__GROUND__", GROUND),
                     ("__FORMATION__", RULES_JS.read_text(encoding="utf-8")),
                     ("__CASES__", json.dumps(cases)),
                     ("__RULE__", json.dumps({k: place[k] for k in ("spread", "back", "rank")})),
                     ("__ART__", json.dumps(art_uris)),
                     ("__SIZES__", json.dumps(sizes)), ("__ORDERS__", json.dumps(orders)),
                     ("__OPENORDER__", json.dumps(place.get("order", "grouped"))),
                     ("__DEPTH__", json.dumps(place.get("depth", {"mode": "haze", "amount": 60}))),
                     # _short, not relative_to: the latter RAISES for a path outside the repo, so a
                     # file pointed elsewhere would crash the page header rather than name itself.
                     ("__FILE__", html.escape(str(board._short(board.PLACEMENT))))):
        page = page.replace(key, val)
    assert "__" not in page.split("<script>")[0].replace("__FONT__", ""), "placeholder left behind"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    print("  %d cases, %d sizes, both orders -- arranged live in the page"
          % (len(CASES), len(sizes)))
    print("  spread %d, set-back %d, rank gap %d  (from %s, tuned at %s px and used at every "
          "size)" % (place["spread"], place["back"], place["rank"], board.PLACEMENT.name,
                     place.get("tuned_at", "?")))
    for note in notes:
        print("  %s" % note)
    if args.serve is not None:
        serve(out, board, args.serve, args.open)   # prints the http URL; the file one is moot
    else:
        board.show(out, args.open)


TEMPLATE = r"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Placement sheet</title>
<style>
@font-face{font-family:"PB";src:url(__FONT__) format("truetype");font-display:block}
html,body{margin:0;min-height:100%;background:#0d0b08;color:#8b8071;
  font:11px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
#head{padding:14px 18px 6px;color:#5f574a}
#head b{color:#c9b27a;font-weight:400}
#grid{display:flex;flex-wrap:wrap;gap:10px;padding:8px 18px 28px;align-items:flex-start}
.case{background:#17130d;border:1px solid #221c14;border-radius:3px;position:relative;
  min-width:148px;display:flex;flex-direction:column}
.field{position:relative;align-self:center;flex:none}
.fig{position:absolute}
.fig img{display:block;width:100%;height:100%}
.floor{position:absolute;left:8%;right:8%;height:1px;background:#2a2318}
.cap{padding:5px 8px 7px;color:#5f574a;font-size:10px;text-align:center}
.cap em{font-style:normal;color:#8b8071}
.cap i{font-style:normal;color:#4f483d}
#ui{position:sticky;top:0;background:rgba(13,11,8,.94);padding:10px 18px;z-index:5;
  border-bottom:1px solid #1e1811;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
#ui .lab{color:#4f483d;margin-right:2px}
#ui input[type=range]{width:104px;accent-color:#c9b27a;background:transparent}
#ui .val{color:#c9b27a;min-width:26px;text-align:right}
#ui button{font:inherit;color:#8b8071;background:#1c1811;border:1px solid #332c20;
  border-radius:3px;padding:3px 9px;cursor:pointer}
#ui button:hover{border-color:#5a4c36}
#ui button[aria-pressed=true]{background:#c9b27a;border-color:#c9b27a;color:#1a1610}
#save{border-color:#4a5a3a}
#saymsg{margin-left:4px}
#saymsg.ok{color:#8fae6a} #saymsg.bad{color:#e0705f} #saymsg.busy{color:#5f574a}
</style>
<svg width=0 height=0 style="position:absolute" aria-hidden=true><defs id=hazedefs></defs></svg>
<div id=ui>
  <span class=lab>sculpt</span><span id=szb></span>
  <span class=lab>order</span><span id=ordb></span>
  <span class=lab>spread</span><input id=sprd type=range min=0 max=200 step=1><span class=val id=sprdv></span>
  <span class=lab>set-back</span><input id=back type=range min=0 max=120 step=1><span class=val id=backv></span>
  <span class=lab>rank</span><input id=rank type=range min=0 max=160 step=1><span class=val id=rankv></span>
  <span class=lab>depth</span><span id=dmb></span>
  <input id=haze type=range min=0 max=100 step=1><span class=val id=hazev></span>
  <span class=lab>full at</span>
  <input id=full type=range min=4 max=200 step=1><span class=val id=fullv></span>
  <button id=bshadow aria-pressed=true>shadow</button>
  <button id=save>save to json</button><span id=saymsg></span>
</div>
<div id=head></div>
<div id=grid></div>
<script>
// ---- the drawing rules, inlined from tools/ui_debug/duty_sculpt_rules.js -------------------------
__FORMATION__
// -------------------------------------------------------------------------------------------
var CASES = __CASES__, RULE = __RULE__, ART = __ART__, SIZES = __SIZES__, ORDERS = __ORDERS__;
var DEPTH = __DEPTH__, MODE = DEPTH.mode, SHADE = DEPTH.amount;
var FULL_AT = DEPTH.full_at || 52;
var SIZE = SIZES.indexOf(210) >= 0 ? 210 : SIZES[SIZES.length - 1], ORDER = __OPENORDER__;
var SPREAD = RULE.spread, BACK = RULE.back, RANK = RULE.rank;
var DPR = devicePixelRatio || 1;
function px(v){ return (v / DPR) + "px"; }

var HAZE_STEPS = DUTY_HAZE.steps, HAZE_MAX = DUTY_HAZE.max;
document.getElementById("hazedefs").innerHTML =
  dutyHazeDefs("__GROUND__", HAZE_STEPS, HAZE_MAX);
function figFilter(y, shadowOn){
  return dutyFilter(y, {ref: FULL_AT, amount: SHADE, mode: MODE, shadow: shadowOn,
                        steps: HAZE_STEPS});
}

function draw(){
  var art = ART[String(SIZE)], shadowOn = document.body.classList.contains("shadow");
  // Measured across every case at the CURRENT settings, so a cell is never sized to a formation
  // it is not drawing -- the sliders can outgrow any constant put here.
  var widest = 0, tallest = 0, cells = [];
  CASES.forEach(function(c){
    var n = c.counts.reduce(function(a, b){ return a + b; }, 0);
    var slots = dutyFormation(n, SPREAD, BACK, RANK)
                  .sort(function(a, b){ return a.x - b.x; });
    var who = dutySeatOrder(c.counts, ORDER);
    var figs = slots.map(function(p, i){
      var a = art[who[i]];
      return {x: p.x, y: p.y, seat: who[i], w: a.w, h: a.h};
    });
    figs.forEach(function(f){
      widest = Math.max(widest, Math.abs(f.x) * 2 + f.w);
      tallest = Math.max(tallest, f.h + f.y);
    });
    cells.push({c: c, figs: figs, who: who});
  });
  var W = widest + 30, H = tallest + 22;

  document.getElementById("head").innerHTML =
      "Every arrangement the rules produce, read from <b>__FILE__</b>.  spread <b>" + SPREAD
    + "</b>, set-back <b>" + BACK + "</b>, rank gap <b>" + RANK + "</b>, order <b>" + ORDER
    + "</b> -- one set, used at every size.  Showing <b>" + SIZE + "</b> px, depth <b>"
    + (SHADE ? MODE + " " + SHADE + "% , full at " + FULL_AT : "off")
    + "</b>.  Drawn at true size, so a sculpt here is the size it is on the board.";

  var h = "";
  cells.forEach(function(cell){
    h += '<div class=case style="width:' + px(W) + '">';
    h += '<div class=field style="width:' + px(W) + ';height:' + px(H) + '">';
    // Painter's order by foot, so a sculpt standing further back never covers a nearer one.
    cell.figs.slice().sort(function(a, b){ return (a.y === b.y) ? a.x - b.x : b.y - a.y; })
      .forEach(function(f){
        h += '<div class=fig style="left:' + px(W/2 + f.x - f.w/2) + ';top:'
           + px(H - 10 - f.h - f.y) + ';width:' + px(f.w) + ';height:' + px(f.h)
           + ';filter:' + figFilter(f.y, shadowOn)
           + '"><img src="' + art[f.seat].uri + '"></div>';
      });
    h += '<div class=floor style="top:' + px(H - 10) + '"></div>';
    h += '</div>';
    h += '<div class=cap><em>' + cell.c.tag + '</em> &#183; ' + cell.c.label
       + '<br><i>' + cell.who.map(function(s){ return "p" + (s + 1); }).join(" ") + '</i></div>';
    h += '</div>';
  });
  document.getElementById("grid").innerHTML = h;
}

function buttons(host, list, get, set){
  var h = "";
  list.forEach(function(v){
    h += '<button data-v="' + v + '" aria-pressed="' + (v === get() ? "true" : "false")
       + '">' + v + '</button>';
  });
  host.innerHTML = h;
  [].forEach.call(host.querySelectorAll("button"), function(b){
    b.onclick = function(){
      var v = b.dataset.v;
      set(isNaN(+v) ? v : +v);
      [].forEach.call(host.querySelectorAll("button"), function(x){
        x.setAttribute("aria-pressed", x.dataset.v === b.dataset.v ? "true" : "false"); });
      draw();
    };
  });
}
function slider(id, value, set){
  var e = document.getElementById(id), v = document.getElementById(id + "v");
  e.value = value; v.textContent = value;
  e.oninput = function(){ set(+e.value); v.textContent = e.value; draw(); };
}
buttons(document.getElementById("szb"), SIZES, function(){ return SIZE; },
        function(v){ SIZE = v; });
buttons(document.getElementById("ordb"), ORDERS, function(){ return ORDER; },
        function(v){ ORDER = v; });
buttons(document.getElementById("dmb"), ["haze", "dark", "off"], function(){ return MODE; },
        function(v){ MODE = v;
                     if (v === "off") SHADE = 0;
                     else if (SHADE === 0) SHADE = DEPTH.amount || 60;
                     document.getElementById("haze").value = SHADE;
                     document.getElementById("hazev").textContent = SHADE; });
slider("sprd", SPREAD, function(v){ SPREAD = v; });
slider("back", BACK,   function(v){ BACK = v; });
slider("rank", RANK,   function(v){ RANK = v; });
slider("haze", SHADE,  function(v){ SHADE = v; });
slider("full", FULL_AT, function(v){ FULL_AT = v; });
document.getElementById("bshadow").onclick = function(){
  var on = document.body.classList.toggle("shadow");
  this.setAttribute("aria-pressed", on ? "true" : "false");
  draw();                      // the shadow is part of the filter chain now, not a CSS class
};

// ---- saving --------------------------------------------------------------------------------
// A page opened as a file: URL cannot write to disk, so the button does the only honest thing
// there: it hands you the JSON as a download and says why. Served by `--serve` it POSTs and the
// generator writes the file, merging into what is already there so the prose notes survive.
function settings(){
  return {spread: SPREAD, back: BACK, rank: RANK, order: ORDER,
          depth: {mode: MODE, amount: SHADE, full_at: FULL_AT}};
}
function say(msg, cls){
  var e = document.getElementById("saymsg");
  e.textContent = msg; e.className = cls || "";
}
document.getElementById("save").onclick = function(){
  var body = JSON.stringify(settings(), null, 2);
  if (location.protocol !== "http:" && location.protocol !== "https:"){
    var a = document.createElement("a");
    a.href = "data:application/json;charset=utf-8," + encodeURIComponent(body);
    a.download = "duty_placement.json";
    a.click();
    say("downloaded -- a file:// page cannot write to the repo. Run with --serve to save in place.",
        "bad");
    return;
  }
  say("saving...", "busy");
  fetch("/save", {method: "POST", headers: {"Content-Type": "application/json"}, body: body})
    .then(function(r){ return r.json().then(function(j){ return {ok: r.ok, j: j}; }); })
    .then(function(res){
      if (!res.ok) throw new Error(res.j.error || "refused");
      say("saved to " + res.j.file + " at " + new Date().toLocaleTimeString(), "ok");
    })
    .catch(function(e){ say("not saved: " + e.message, "bad"); });
};

document.body.classList.add("shadow");
draw();
addEventListener("resize", draw);
(function(){ if (!document.fonts) return;
  document.fonts.load('400 20px "PB"').then(function(){ return document.fonts.ready; })
    .then(draw).catch(function(){}); })();
</script>
"""


if __name__ == "__main__":
    main()
