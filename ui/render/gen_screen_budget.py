#!/usr/bin/env python3
"""What the duty wheel actually gets on a given screen, drawn to scale.

    python3 ui/render/gen_screen_budget.py            # write ui/generated/screen-budget.html
    python3 ui/render/gen_screen_budget.py --open     # ...and open it

WHAT THE PAGE IS FOR

Screen size is the one dimension of this layout that cannot be reasoned about from the source,
because it is not in the source. The stage is a fixed-aspect canvas that is zoom-to-fitted into
the window -- `k = min(innerWidth / canvas_width, innerHeight / canvas_height)` -- so the only
thing a display contributes is one number, and which of the two terms wins decides whether a
wider monitor is worth anything at all. It usually is not. Every screen wider than the canvas
aspect is fitted by its HEIGHT, which means a 27-inch 1440p panel, a 34-inch 21:9 and a 49-inch
32:9 hand the wheel exactly the same pixels and differ only in how much letterbox they paint.
That is not obvious from any file, it is very obvious from a picture, and it has cost real work.

WHY THIS IS A GENERATOR AND NOT A COMMITTED PAGE

The page is only worth opening if its numbers are the board's numbers. It draws the board column,
the action box, the banner and the wheel at true relative scale, and every one of those comes out
of `gen_game_view.geometry()`. Written as a hand-kept HTML file those constants would be a second
copy of DEFAULTS, and a second copy of DEFAULTS is a thing that is right on the day it is written
and wrong the first time anybody drags a slider in the layout tool. So the layout is READ from
`gen_game_view` and stamped in, and `ui/generated/` is git-ignored precisely so that no stale
copy of this can sit in the tree looking authoritative.

THE ONE DUPLICATION THAT CANNOT BE REMOVED, AND WHAT IS DONE ABOUT IT

The page has sliders. Moving one has to re-run `geometry()` in the browser, so the arithmetic
genuinely exists twice: once in Python and once in JavaScript. That cannot be refactored away
without either giving up the sliders or shipping a Python interpreter.

What it can do is fail loudly. This module runs the real `geometry()` over a spread of layouts --
the defaults, compare mode, Special Activities off, a widened canvas, a narrowed board, no banner
-- and stamps the answers into the page as expectations. The page recomputes them with its own
JavaScript on load and, if any disagree, replaces itself with the mismatch rather than drawing a
plausible diagram from arithmetic that has drifted. `tests/test_ground_guards.py` asks the BUILT
page the same question, so the check runs in CI and not only when somebody happens to look.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
RENDER = REPO / "ui" / "render"
OUT = REPO / "ui" / "generated" / "screen-budget.html"

sys.path.insert(0, str(RENDER))
import gen_game_view as gv          # noqa: E402

# The keys the page actually drives. Named rather than taken wholesale from DEFAULTS because the
# page has a control or a rectangle for each of these and would silently ignore anything else --
# and a setting that is stamped in but never drawn is worse than one that is absent, since it
# reads as covered. `assert_keys_exist` below is what stops this list rotting the other way.
LAYOUT_KEYS = (
    "canvas_width", "canvas_height", "board_width", "board_gap", "seats",
    "special_height", "column_gap_1", "column_gap_2", "row_gap",
    "banner_height", "margin_top", "margin_bottom", "special_activities",
)

# Reference screens, as CSS pixels of BROWSER VIEWPORT rather than of panel -- which is what the
# fit actually divides by, and is smaller than the panel by whatever the window chrome takes. They
# are estimates and the page says so; the numbers that matter are the ones a person pins by
# opening the page on the display in question.
REFERENCE = [
    {"name": 'MacBook Pro 14"', "vw": 1512, "vh": 860},
    {"name": 'MacBook Pro 16"', "vw": 1728, "vh": 982},
    {"name": '27" 1440p', "vw": 2560, "vh": 1305},
    {"name": '34" ultrawide 21:9', "vw": 3440, "vh": 1305},
    {"name": '49" super-ultrawide 32:9', "vw": 5120, "vh": 1305},
]

# The layouts the built page has to reproduce. Chosen so that each one moves a DIFFERENT term:
# compare mode widens the canvas and the board together, "wide canvas" widens only the canvas and
# is the case that flips bound_by, "narrow board" is the other lever on the same flip, and
# "no banner" is the only one that changes the height term. A spread that all landed on the same
# branch would pass while testing one line.
CASES = (
    ("defaults", {}),
    ("compare", {k: v for k, v in gv.DEFAULTS["compare"].items() if k != "label"}),
    ("special activities off", {"special_activities": False}),
    ("wide canvas", {"canvas_width": 2200}),
    ("narrow board", {"board_width": 300.0}),
    ("no banner", {"banner_height": 0.0}),
)

WANTED = ("wheel", "wheel_room", "main_h", "panel_w", "bound_by", "left_h", "left_lift", "bh")


def assert_keys_exist() -> None:
    """Every key the page drives must still be a key gen_game_view has.

    A rename in DEFAULTS would otherwise reach the page as a KeyError at build time, which is
    fine, or -- worse -- as a stamped layout missing a term the JavaScript then reads as
    undefined and quietly turns into NaN somewhere inside an SVG attribute, where it draws
    nothing and says nothing.
    """
    missing = [k for k in LAYOUT_KEYS if k not in gv.DEFAULTS]
    if missing:
        raise SystemExit(
            "gen_game_view.DEFAULTS no longer has %s. The page has a control or a rectangle for "
            "each key in LAYOUT_KEYS, so this list has to be brought back into step with it "
            "rather than letting the page draw with a term it cannot resolve."
            % ", ".join(missing))


def layout_for(over: dict) -> dict:
    L = {k: gv.DEFAULTS[k] for k in LAYOUT_KEYS}
    L.update({k: v for k, v in over.items() if k in LAYOUT_KEYS})
    return L


def expectations() -> list:
    """The real geometry() over CASES, as the page's own self-test."""
    rows = []
    for label, over in CASES:
        full = dict(gv.DEFAULTS)
        full.update({k: v for k, v in over.items() if k != "label"})
        G = gv.geometry(full)
        rows.append({
            "label": label,
            "L": layout_for(over),
            "want": {k: (G[k] if isinstance(G[k], str) else round(float(G[k]), 6))
                     for k in WANTED},
        })
    return rows


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Screen budget</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:#2b2724;color:#e9e0cc;
     font:14px/1.6 "Iowan Old Style",Palatino,Georgia,serif;padding:20px 22px 40px}
h1{font:600 20px/1.3 Georgia,serif;margin:0 0 2px;color:#efe6d2}
.sub{color:#a99e86;font-size:13px;margin:0 0 18px;max-width:74ch}
h2{font:600 12px/1.3 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;
   color:#a08f68;margin:26px 0 10px;border-top:1px solid #3a352a;padding-top:12px}
.panel{background:#221f1c;border:1px solid #3a352a;border-radius:10px;padding:14px 16px}
.live{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-end}
.live .big{font:600 26px/1.1 Georgia,serif;color:#efe6d2}
.live .lbl{font:600 11px/1.3 system-ui,sans-serif;letter-spacing:.07em;text-transform:uppercase;
           color:#8d8471;margin-bottom:3px}
button{font:inherit;font-size:13px;background:#3a4f3f;border:1px solid #4d6b53;color:#e9e0cc;
       border-radius:7px;padding:7px 13px;cursor:pointer}
button:hover{filter:brightness(1.15)}
button.ghost{background:#2e2a26;border-color:#4a443a}
input[type=text]{font:inherit;font-size:13px;background:#1d1a17;border:1px solid #4a443a;
                 color:#e9e0cc;border-radius:7px;padding:7px 9px;width:150px}
.controls{display:flex;flex-wrap:wrap;gap:18px 26px;align-items:center}
.ctl{display:flex;flex-direction:column;gap:4px;min-width:150px}
.ctl label{font:600 11px/1.3 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;
           color:#8d8471}
.ctl .row{display:flex;align-items:center;gap:9px}
input[type=range]{width:150px;accent-color:#7d9b52}
.val{font:600 13px/1 Georgia,serif;color:#efe6d2;min-width:44px}
.cards{display:flex;flex-wrap:wrap;gap:14px;margin-top:4px}
.card{background:#221f1c;border:1px solid #3a352a;border-radius:10px;padding:12px 13px 11px;
      width:326px}
.card.me{border-color:#7d9b52}
.card h3{font:600 14px/1.3 Georgia,serif;margin:0 0 1px;color:#efe6d2;
         display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.card h3 .tag{font:600 10px/1.3 system-ui,sans-serif;letter-spacing:.07em;text-transform:uppercase;
              color:#7d9b52;flex:none}
.card h3 .tag.est{color:#8d8471}
.card .dims{color:#a99e86;font-size:12.5px;margin:0 0 9px}
.card svg{display:block;width:100%;height:auto;background:#17150f;border-radius:5px}
.stat{display:flex;justify-content:space-between;gap:10px;font-size:12.6px;
      border-top:1px solid #322d26;padding:5px 0 0;margin-top:8px}
.stat b{color:#efe6d2;font-weight:600}
.stat.warn b{color:#d4695e}
.stat.good b{color:#8fbf73}
.drop{background:none;border:0;color:#8d8471;cursor:pointer;font:inherit;font-size:12px;padding:0}
.drop:hover{color:#d4695e}
.note{color:#a99e86;font-size:12.6px;max-width:82ch;margin:10px 0 0}
.note b{color:#cdc2a9;font-weight:600}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:9px;font-size:12.3px;color:#a99e86}
.legend i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;
          vertical-align:-1px}
#nest,#curve{display:block;width:100%;height:auto}
#drift{background:#3a1d1a;border:1px solid #d4695e;border-radius:10px;padding:14px 16px;
       margin:0 0 18px;color:#f0c9c3}
#drift b{color:#ffd9d2}
#drift pre{margin:8px 0 0;font:12px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap}
</style>
</head>
<body>

<div id="drift" hidden></div>

<h1>Screen budget</h1>
<p class="sub">What the duty wheel actually gets, on each screen. The stage is a fixed-aspect
canvas that is zoom-to-fitted into the window, so width past that aspect is letterbox and buys
nothing &mdash; which is the part that keeps biting. Open this on each display and press
<b>Pin this screen</b>; the pinned rectangles are true measurements, the rest are estimates.
Every layout number is read from <code>gen_game_view</code> at build time.</p>

<div class="panel live" id="live"></div>

<h2>The layout being measured</h2>
<div class="panel controls" id="controls"></div>
<p class="note" id="derived"></p>

<h2>The screens, to one scale</h2>
<svg id="nest" viewBox="0 0 1200 460" preserveAspectRatio="xMinYMin meet"></svg>
<div class="legend">
  <span><i style="background:#7d9b52"></i>this window</span>
  <span><i style="background:#c9b27a"></i>pinned</span>
  <span><i style="background:#6b6354"></i>estimated</span>
</div>

<h2>Wheel size against window height</h2>
<svg id="curve" viewBox="0 0 1200 300" preserveAspectRatio="xMinYMin meet"></svg>
<p class="note">Vertical axis is the wheel in px. The line is a <b>ceiling</b>, not a prediction:
any window wider than the canvas aspect sits exactly on it, so its height is the only thing that
moved it. A window <i>narrower</i> than the canvas is width-bound and its dot drops below the line
by however much width it is short &mdash; so the gap between a dot and the line is the entire
value of that screen's width, and on every screen here it is zero.</p>

<h2>What each one gives the wheel</h2>
<div class="cards" id="cards"></div>

<p class="note" id="footer"></p>

<script>
"use strict";

/* ------------------------------------------------------------------ the model
   STAMPED from ui/render/gen_game_view.py at build time -- DEFAULTS, the stage
   constants, and the answers the real geometry() gives for a spread of layouts.
   Nothing here is typed by hand, which is the only reason the diagram can be
   trusted to be about the board rather than about a copy of it. */
var CONST = __CONST__;
var STAGE_PAD = CONST.STAGE_PAD,
    FRAME_START = CONST.FRAME_START, FRAME_END = CONST.FRAME_END,
    VB_W = CONST.VB_W, VB_H = CONST.VB_H;
var L = __LAYOUT__;
var REFERENCE = __REFERENCE__;
var EXPECT = __EXPECT__;

/* geometry(), ported. The sliders need it here, so it exists twice; selfCheck()
   below is what keeps the two copies honest. Same names as the Python, so a
   number on this page can be read straight against one the generator prints. */
function geometry(L){
  var inner_w = L.canvas_width - 2 * STAGE_PAD;
  var inner_h = L.canvas_height - L.margin_top - L.margin_bottom;
  var bw = L.board_width;
  var panel_w = bw * (FRAME_END - FRAME_START);
  var bh = Math.round(bw * VB_H / VB_W * 10) / 10;
  /* top_h is NOT conditional on special_activities, and that is worth a line
     because it reads as though it should be: turning the panel off does not give
     the wheel a pixel. The top row keeps its height either way; what changes is
     only that the BOARD column stops starting below it and runs the full inner
     height instead. */
  var top_h = L.special_height;
  var main_h = inner_h - top_h;
  var banner_h = L.banner_height;
  var wheel_room = inner_w - bw - panel_w - L.column_gap_1 - L.column_gap_2;
  var wheel = Math.max(0, Math.min(wheel_room, main_h - banner_h));
  var left_top = L.row_gap;
  return {
    inner_w: inner_w, inner_h: inner_h, bw: bw, bh: bh, panel_w: panel_w,
    top_h: top_h, main_h: main_h, banner_h: banner_h,
    wheel_room: wheel_room, wheel: wheel,
    bound_by: wheel_room <= main_h - banner_h ? "width" : "height",
    left_top: left_top,
    left_h: L.special_activities ? main_h - left_top : inner_h - left_top,
    left_lift: L.special_activities ? 0.0 : top_h,
    boards_h: L.seats * bh + (L.seats - 1) * L.board_gap
  };
}

/* The whole point: the stage is laid out at canvas size and then scaled to fit
   the window, centred. k is the only thing a screen contributes. */
function fitScale(vw, vh, L){
  return Math.min(vw / L.canvas_width, vh / L.canvas_height);
}

/* --------------------------------------------------------------- self-check
   The page recomputes what the real geometry() already answered. On a mismatch
   it says so and stops, rather than drawing a diagram that looks fine and is
   about arithmetic that has drifted -- which is the only failure mode a picture
   like this has, and the one it would never show. */
function selfCheck(){
  var bad = [];
  EXPECT.forEach(function (c){
    var got = geometry(c.L);
    Object.keys(c.want).forEach(function (k){
      var a = c.want[k], b = got[k];
      var same = (typeof a === "string") ? a === b : Math.abs(a - b) < 1e-6;
      if (!same) bad.push(c.label + ": " + k + " = " + b + ", gen_game_view says " + a);
    });
  });
  if (!bad.length) return true;
  var el = document.getElementById("drift");
  el.hidden = false;
  el.innerHTML = "<b>This page no longer agrees with gen_game_view.geometry().</b> " +
    "The sliders need the layout arithmetic in the browser, so it exists in both " +
    "places, and the two have parted company. Nothing below is drawn, because a " +
    "diagram from drifted arithmetic is worse than none." +
    "<pre>" + bad.map(function (s){
      return s.replace(/[&<>]/g, function (c){
        return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]; });
    }).join("\n") + "</pre>";
  return false;
}

/* ------------------------------------------------------------- the screens */
var KEY = "pilgrim.screen-budget.pins";
function loadPins(){
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; }
}
function savePins(p){
  try { localStorage.setItem(KEY, JSON.stringify(p)); } catch (e) { /* private window */ }
}
var pins = loadPins();

function allScreens(){
  var out = [{ name: "This window", vw: window.innerWidth, vh: window.innerHeight, live: true }];
  pins.forEach(function (p){ out.push({ name: p.name, vw: p.vw, vh: p.vh, pinned: true }); });
  REFERENCE.forEach(function (r){
    // a reference the same size as something already shown is noise
    var dup = out.some(function (o){
      return Math.abs(o.vw - r.vw) < 40 && Math.abs(o.vh - r.vh) < 40; });
    if (!dup) out.push({ name: r.name, vw: r.vw, vh: r.vh });
  });
  return out;
}

/* --------------------------------------------------------------- rendering */
var esc = function (s){ return String(s).replace(/[&<>"]/g, function (c){
  return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); };
var n0 = function (v){ return Math.round(v).toLocaleString(); };
function colourFor(s){ return s.live ? "#7d9b52" : s.pinned ? "#c9b27a" : "#6b6354"; }

function drawNest(screens){
  var svg = document.getElementById("nest");
  var maxW = Math.max.apply(null, screens.map(function (s){ return s.vw; }));
  var maxH = Math.max.apply(null, screens.map(function (s){ return s.vh; }));
  var PADL = 8, PADT = 10, LBL = 268, BOX_W = 1200, BOX_H = 430;
  var k = Math.min((BOX_W - PADL - LBL) / maxW, (BOX_H - PADT - 22) / maxH);
  var parts = [], taken = [];
  // biggest first, so the small ones are drawn last and stay visible on top
  screens.slice().sort(function (a, b){ return b.vw * b.vh - a.vw * a.vh; }).forEach(function (s){
    var w = s.vw * k, h = s.vh * k, c = colourFor(s);
    parts.push('<rect x="' + PADL + '" y="' + PADT + '" width="' + w.toFixed(1) +
               '" height="' + h.toFixed(1) + '" fill="' + c + '" fill-opacity="0.07" stroke="' + c +
               '" stroke-width="' + (s.live ? 2 : 1.2) + '" rx="3"/>');
    /* THE LABEL GOES BESIDE ITS OWN BOTTOM-RIGHT CORNER, which is the only
       corner that tells two rectangles sharing a top-left apart. Three of the
       reference screens are 1440p panels and share a height exactly, so without
       the nudge their three names print on one line on top of each other. */
    var ly = PADT + h - 3;
    while (taken.some(function (t){ return Math.abs(t - ly) < 15; })) ly += 15;
    taken.push(ly);
    var lx = PADL + w + 8;
    parts.push('<line x1="' + (PADL + w).toFixed(1) + '" y1="' + (PADT + h).toFixed(1) +
               '" x2="' + (lx - 3).toFixed(1) + '" y2="' + ly.toFixed(1) +
               '" stroke="' + c + '" stroke-width="0.7" stroke-opacity="0.5"/>');
    parts.push('<text x="' + lx.toFixed(1) + '" y="' + ly.toFixed(1) +
               '" font-size="12.5" font-family="Georgia,serif" fill="' + c + '">' +
               esc(s.name) + ' &#183; ' + s.vw + '&#215;' + s.vh + '</text>');
  });
  var bottom = Math.max(PADT + maxH * k, Math.max.apply(null, taken)) + 16;
  svg.setAttribute("viewBox", "0 0 " + BOX_W + " " + bottom.toFixed(0));
  svg.innerHTML = parts.join("");
}

/* Wheel size as a function of window HEIGHT. The line is what height alone buys:
   wheel x vh / canvas_height, straight through the origin. It is a CEILING, not
   a prediction. A window wider than the canvas aspect sits exactly ON it, which
   is why an ultrawide and a laptop are on the same line and only their heights
   separate them; a window NARROWER than the canvas is width-bound and its dot
   falls below by however much width it is short. */
function drawCurve(screens, G){
  var svg = document.getElementById("curve");
  var W = 1200, H = 300, ML = 62, MR = 210, MT = 14, MB = 34;
  var hMin = 600;
  var hMax = Math.max(1700, Math.max.apply(null, screens.map(function (s){ return s.vh; })) + 150);
  var wMaxPx = 0, pts = [];
  for (var vh = hMin; vh <= hMax; vh += 5) {
    var px = G.wheel * (vh / L.canvas_height);
    pts.push([vh, px]);
    if (px > wMaxPx) wMaxPx = px;
  }
  var X = function (v){ return ML + (v - hMin) / (hMax - hMin) * (W - ML - MR); };
  var top = wMaxPx * 1.06 || 1;
  var Y = function (v){ return H - MB - v / top * (H - MT - MB); };
  var p = [];
  p.push('<rect x="' + ML + '" y="' + MT + '" width="' + (W - ML - MR) + '" height="' +
         (H - MT - MB) + '" fill="#17150f" rx="4"/>');
  [0, 0.25, 0.5, 0.75, 1].forEach(function (f){
    var v = top * f;
    p.push('<line x1="' + ML + '" y1="' + Y(v).toFixed(1) + '" x2="' + (W - MR) + '" y2="' +
           Y(v).toFixed(1) + '" stroke="#3a352a" stroke-width="0.8"/>');
    p.push('<text x="' + (ML - 8) + '" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end" ' +
           'font-size="11.5" font-family="Georgia,serif" fill="#8d8471">' + n0(v) + '</text>');
  });
  p.push('<polyline fill="none" stroke="#7d9b52" stroke-width="2" points="' +
         pts.map(function (q){ return X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1); }).join(" ") +
         '"/>');
  var taken = [];
  screens.slice().sort(function (a, b){ return b.vh - a.vh; }).forEach(function (s){
    if (s.vh < hMin || s.vh > hMax) return;
    var px = G.wheel * fitScale(s.vw, s.vh, L), c = colourFor(s), x = X(s.vh), y = Y(px);
    p.push('<line x1="' + x.toFixed(1) + '" y1="' + (H - MB) + '" x2="' + x.toFixed(1) +
           '" y2="' + y.toFixed(1) + '" stroke="' + c +
           '" stroke-width="0.9" stroke-dasharray="3 3"/>');
    p.push('<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="4" fill="' + c + '"/>');
    var ly = y + 4;
    while (taken.some(function (t){ return Math.abs(t - ly) < 15; })) ly += 15;
    taken.push(ly);
    p.push('<text x="' + (W - MR + 10) + '" y="' + ly.toFixed(1) + '" font-size="12" ' +
           'font-family="Georgia,serif" fill="' + c + '">' + esc(s.name) + ' &#183; ' +
           n0(px) + ' px</text>');
  });
  p.push('<text x="' + ML + '" y="' + (H - 8) + '" font-size="11.5" font-family="Georgia,serif" ' +
         'fill="#8d8471">' + hMin + ' px of window height</text>');
  p.push('<text x="' + (W - MR) + '" y="' + (H - 8) + '" text-anchor="end" font-size="11.5" ' +
         'font-family="Georgia,serif" fill="#8d8471">' + hMax + '</text>');
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  svg.innerHTML = p.join("");
}

function card(s, G){
  var k = fitScale(s.vw, s.vh, L);
  var stageW = L.canvas_width * k, stageH = L.canvas_height * k;
  var wheelPx = G.wheel * k;
  var gutterW = s.vw - stageW, gutterH = s.vh - stageH;
  var heightBound = (s.vw / s.vh) > (L.canvas_width / L.canvas_height);

  var W = 300, sc = W / s.vw, H = s.vh * sc;
  var sw = stageW * sc, sh = stageH * sc;
  var ox = (W - sw) / 2, oy = (H - sh) / 2;
  var u = function (v){ return v * k * sc; };          // canvas units -> drawing px
  var q = function (v){ return u(v).toFixed(2); };
  var p = [];
  p.push('<rect width="' + W + '" height="' + H.toFixed(1) + '" fill="#4d4844"/>');
  p.push('<rect x="' + ox.toFixed(1) + '" y="' + oy.toFixed(1) + '" width="' + sw.toFixed(1) +
         '" height="' + sh.toFixed(1) + '" fill="#1d1a15"/>');
  var ix = ox + u(STAGE_PAD), iy = oy + u(L.margin_top);
  // the top row: solid when Special Activities is drawn, ghosted when it is not,
  // because the wheel's height does not depend on which
  p.push('<rect x="' + ix.toFixed(1) + '" y="' + iy.toFixed(1) + '" width="' + q(G.inner_w) +
         '" height="' + q(G.top_h) + '" fill="#3a352a" fill-opacity="' +
         (L.special_activities ? 1 : 0.28) + '" rx="1"/>');
  var mainY = iy + u(G.top_h);
  p.push('<rect x="' + ix.toFixed(1) + '" y="' +
         (mainY - u(G.left_lift) + u(G.left_top)).toFixed(1) + '" width="' + q(G.bw) +
         '" height="' + q(G.left_h) + '" fill="#6b6354" fill-opacity="0.55" rx="1"/>');
  var ax = ix + u(G.bw + L.column_gap_1);
  p.push('<rect x="' + ax.toFixed(1) + '" y="' + mainY.toFixed(1) + '" width="' + q(G.panel_w) +
         '" height="' + q(G.main_h) + '" fill="#4a4436" fill-opacity="0.75" rx="1"/>');
  var wx = ax + u(G.panel_w + L.column_gap_2);
  p.push('<rect x="' + wx.toFixed(1) + '" y="' + mainY.toFixed(1) + '" width="' + q(G.wheel) +
         '" height="' + q(G.banner_h) + '" fill="#8d8471" fill-opacity="0.6" rx="1"/>');
  var wy = mainY + u(G.banner_h);
  p.push('<rect x="' + wx.toFixed(1) + '" y="' + wy.toFixed(1) + '" width="' + q(G.wheel) +
         '" height="' + q(G.wheel) + '" fill="#7d9b52" fill-opacity="0.85" rx="2"/>');
  // the height the wheel could not reach, which the boxes take
  if (G.main_h - G.banner_h - G.wheel > 0.5) {
    p.push('<rect x="' + wx.toFixed(1) + '" y="' + (wy + u(G.wheel)).toFixed(1) + '" width="' +
           q(G.wheel) + '" height="' + q(G.main_h - G.banner_h - G.wheel) +
           '" fill="#d4695e" fill-opacity="0.35" rx="1"/>');
  }
  p.push('<rect x="' + ox.toFixed(1) + '" y="' + oy.toFixed(1) + '" width="' + sw.toFixed(1) +
         '" height="' + sh.toFixed(1) + '" fill="none" stroke="#a08f68" stroke-width="0.8"/>');
  p.push('<rect x="0.4" y="0.4" width="' + (W - 0.8) + '" height="' + (H - 0.8).toFixed(1) +
         '" fill="none" stroke="' + colourFor(s) + '" stroke-width="1.4" rx="3"/>');

  var tag = s.live ? '<span class="tag">measured</span>'
          : s.pinned ? '<span class="tag">pinned</span>'
          : '<span class="tag est">estimate</span>';
  var rm = s.pinned ? ' <button class="drop" data-drop="' + esc(s.name) + '">remove</button>' : '';

  return '<div class="card' + (s.live ? ' me' : '') + '">' +
    '<h3><span>' + esc(s.name) + '</span>' + tag + '</h3>' +
    '<p class="dims">' + s.vw + ' &#215; ' + s.vh + ' css px &#183; ' +
      (s.vw / s.vh).toFixed(2) + ':1 &#183; stage at ' + (k * 100).toFixed(1) + '%' + rm + '</p>' +
    '<svg viewBox="0 0 ' + W + ' ' + H.toFixed(1) + '">' + p.join("") + '</svg>' +
    '<div class="stat good"><span>duty wheel</span><b>' + n0(wheelPx) + ' px</b></div>' +
    '<div class="stat"><span>one duty tile</span><b>' + n0(wheelPx * CONST.TILE_FRAC) +
      ' px</b></div>' +
    '<div class="stat ' + (gutterW > 40 ? 'warn' : '') + '"><span>' +
      (heightBound ? 'width doing nothing' : 'height doing nothing') + '</span><b>' +
      n0(heightBound ? gutterW : gutterH) + ' px</b></div>' +
    '</div>';
}

function render(){
  var G = geometry(L);
  var screens = allScreens();
  var s0 = screens[0], k0 = fitScale(s0.vw, s0.vh, L);

  document.getElementById("live").innerHTML =
    '<div><div class="lbl">this window</div><div class="big">' + s0.vw + ' &#215; ' + s0.vh +
      '</div></div>' +
    '<div><div class="lbl">screen</div><div class="big">' + screen.width + ' &#215; ' +
      screen.height + '</div></div>' +
    '<div><div class="lbl">aspect</div><div class="big">' + (s0.vw / s0.vh).toFixed(2) +
      ':1</div></div>' +
    '<div><div class="lbl">wheel here</div><div class="big">' + n0(G.wheel * k0) +
      ' px</div></div>' +
    '<div style="display:flex;gap:8px;align-items:center">' +
      '<input type="text" id="pinname" placeholder="name this screen">' +
      '<button id="pin">Pin this screen</button>' +
      (pins.length ? '<button class="ghost" id="clear">Clear pins</button>' : '') +
    '</div>';

  document.getElementById("derived").innerHTML =
    'Canvas <b>' + L.canvas_width + ' &#215; ' + L.canvas_height + '</b> (' +
    (L.canvas_width / L.canvas_height).toFixed(3) + ':1) &#183; wheel <b>' + G.wheel.toFixed(1) +
    '</b> canvas units, limited by <b>' + G.bound_by + '</b> &#183; it has ' +
    G.wheel_room.toFixed(1) + ' of width and ' + (G.main_h - G.banner_h).toFixed(1) +
    ' of height to work with, and takes the smaller. ' +
    (G.bound_by === "height"
      ? 'Widening the canvas will not help until the height term moves.'
      : 'It is pinched by width, so a wider canvas &mdash; or a narrower board &mdash; is the lever.');

  document.getElementById("cards").innerHTML =
    screens.map(function (s){ return card(s, G); }).join("");
  drawNest(screens);
  drawCurve(screens, G);

  document.getElementById("footer").innerHTML =
    'A screen is <b>height-bound</b> whenever it is wider than the canvas aspect of ' +
    (L.canvas_width / L.canvas_height).toFixed(3) + ':1, and every ordinary display is. ' +
    'That is the whole trap: two monitors thousands of pixels apart in width hand the wheel the ' +
    'same number, because both are fitted by their <b>height</b>. Extra width only becomes ' +
    'reachable by changing the canvas aspect, which is what <code>canvas_width</code> does &mdash; ' +
    'drag it and watch the widest card move while the laptop card stands still.';

  wire();
}

function wire(){
  var pinBtn = document.getElementById("pin");
  if (pinBtn) pinBtn.onclick = function (){
    var el = document.getElementById("pinname");
    var name = (el.value || "").trim() || (window.innerWidth > 2200 ? "Wide screen" : "Laptop");
    pins = pins.filter(function (p){ return p.name !== name; });
    pins.push({ name: name, vw: window.innerWidth, vh: window.innerHeight });
    savePins(pins); render();
  };
  var clr = document.getElementById("clear");
  if (clr) clr.onclick = function (){ pins = []; savePins(pins); render(); };
  Array.prototype.forEach.call(document.querySelectorAll("[data-drop]"), function (b){
    b.onclick = function (){
      pins = pins.filter(function (p){ return p.name !== b.getAttribute("data-drop"); });
      savePins(pins); render();
    };
  });
}

/* ----------------------------------------------------------------- controls */
var CONTROLS = [
  { key: "canvas_width",  label: "canvas width",  min: 1400, max: 2600, step: 10 },
  { key: "canvas_height", label: "canvas height", min: 900,  max: 1600, step: 10 },
  { key: "board_width",   label: "board width",   min: 300,  max: 700,  step: 1 },
  { key: "banner_height", label: "banner",        min: 0,    max: 200,  step: 1 }
];
var RESET = JSON.parse(JSON.stringify(L));

function buildControls(){
  var host = document.getElementById("controls");
  host.innerHTML = CONTROLS.map(function (c){
    return '<div class="ctl"><label>' + c.label + '</label><div class="row">' +
      '<input type="range" id="c_' + c.key + '" min="' + c.min + '" max="' + c.max +
      '" step="' + c.step + '" value="' + L[c.key] + '">' +
      '<span class="val" id="v_' + c.key + '">' + L[c.key] + '</span></div></div>';
  }).join("") +
  '<div class="ctl"><label>special activities</label><div class="row">' +
  '<button class="ghost" id="c_sa">' + (L.special_activities ? "on" : "off") + '</button>' +
  '<button class="ghost" id="reset">reset</button></div></div>';

  CONTROLS.forEach(function (c){
    document.getElementById("c_" + c.key).addEventListener("input", function (e){
      L[c.key] = parseFloat(e.target.value);
      document.getElementById("v_" + c.key).textContent = L[c.key];
      render();
    });
  });
  document.getElementById("c_sa").onclick = function (){
    L.special_activities = !L.special_activities;
    this.textContent = L.special_activities ? "on" : "off";
    render();
  };
  document.getElementById("reset").onclick = function (){
    Object.keys(RESET).forEach(function (k){ L[k] = RESET[k]; });
    CONTROLS.forEach(function (c){
      document.getElementById("c_" + c.key).value = L[c.key];
      document.getElementById("v_" + c.key).textContent = L[c.key];
    });
    document.getElementById("c_sa").textContent = L.special_activities ? "on" : "off";
    render();
  };
}

if (selfCheck()) {
  buildControls();
  render();
  window.addEventListener("resize", render);
}
</script>
</body>
</html>
"""


def build() -> str:
    assert_keys_exist()
    # sort_keys and a fixed separator: the page has to build BYTE-IDENTICAL twice, because
    # `rebuild_ui_pages.py --check` diffs two builds of it and a dict iterating differently
    # would read as a real change forever after.
    dump = lambda o: json.dumps(o, sort_keys=True, indent=None, separators=(", ", ": "))
    const = {
        "STAGE_PAD": gv.STAGE_PAD,
        "FRAME_START": gv.FRAME_START, "FRAME_END": gv.FRAME_END,
        "VB_W": gv.VB_W, "VB_H": gv.VB_H,
        # One duty tile as a fraction of the wheel's box, asked of the grid rather than written
        # down: the wheel is nine tiles and "how big is a tile" is the question people actually
        # have about a screen, but the number is gen_duty_grid's and moves when it re-lays.
        "TILE_FRAC": round(tile_fraction(), 6),
    }
    return (PAGE.replace("__CONST__", dump(const))
                .replace("__LAYOUT__", dump(layout_for({})))
                .replace("__REFERENCE__", dump(REFERENCE))
                .replace("__EXPECT__", dump(expectations())))


def tile_fraction() -> float:
    """One laid tile's width as a fraction of the grid's box.

    Measured off `laid_shapes()` rather than hard-coded, because the arrangement has already
    moved once and a constant here would have gone on reporting the old tile confidently.
    """
    import re
    import gen_duty_grid as dg
    d = dg.laid_shapes(pop_set=gv.POP_SET)[0]
    xs = [float(v) for v in re.findall(r"-?\d+\.?\d*", d)][0::2]
    return (max(xs) - min(xs)) / dg.load()["box"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--open", action="store_true", help="open the page when it is written")
    args = ap.parse_args()

    page = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")

    G = gv.geometry(gv.DEFAULTS)
    print("wrote %s  (%.0f KB)" % (OUT, len(page.encode("utf-8")) / 1024))
    print("  canvas   %s x %s  (%.3f:1)"
          % (gv.DEFAULTS["canvas_width"], gv.DEFAULTS["canvas_height"],
             gv.DEFAULTS["canvas_width"] / gv.DEFAULTS["canvas_height"]))
    print("  wheel    %.1f canvas units, limited by %s (%.1f of width against %.1f of height)"
          % (G["wheel"], G["bound_by"], G["wheel_room"], G["main_h"] - G["banner_h"]))
    print("  one tile %.1f%% of the wheel" % (tile_fraction() * 100))
    print("  page checks itself against %d layouts: %s"
          % (len(CASES), ", ".join(label for label, _ in CASES)))
    for s in REFERENCE:
        k = min(s["vw"] / gv.DEFAULTS["canvas_width"], s["vh"] / gv.DEFAULTS["canvas_height"])
        print("  %-26s %4d x %4d -> wheel %4.0f px, %5.0f px of width unused"
              % (s["name"], s["vw"], s["vh"], G["wheel"] * k,
                 s["vw"] - gv.DEFAULTS["canvas_width"] * k))
    if args.open:
        import webbrowser
        webbrowser.open(OUT.resolve().as_uri())


if __name__ == "__main__":
    main()
