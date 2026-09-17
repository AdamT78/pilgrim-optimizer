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
aspect is fitted by its HEIGHT, so displays thousands of pixels apart in width hand the wheel the
same size and differ only in how much letterbox they paint. That is not obvious from any file, it
is very obvious from a picture, and it has cost real work.

TWO THINGS THE PAGE FOUND THAT NOTHING ELSE HERE SAYS

The best canvas width has no screen term in it. The wheel grows with the canvas only until it
becomes height-bound; past that it is fixed and every further unit of width is paid for in scale.
The optimum is where those meet, which is a fact about the canvas and the wheel's aspect alone --
so displays cannot disagree about it, and there is nothing for a per-screen build to resolve.
`best_canvas` computes it and the page draws the measured hills beside it; they agree at every
aspect tried. At aspect 1.00 it returns 1600, which is exactly the canvas this game already uses.

And a bigger screen is not a higher-resolution one. The 14-inch laptop here reports a pixel ratio
of 2 and the 34-inch ultrawide reports 1, so the laptop draws the wheel into 1204 real pixels
against the ultrawide's 964 -- 60% smaller on screen and a fifth sharper. The laptop is what the
artwork has to satisfy. Only the measurement says so, which is why two screens in REFERENCE are
measured rather than estimated.

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

# Keys the page uses IF the module has them, and does without if it does not. `wheel_aspect` is
# the whole list: the page can explore a landscape wheel, gen_game_view cannot build one yet, and
# writing it this way means the day it can, the page reads the real value instead of a proposal
# and relabels itself. Optional rather than required on purpose -- a page that refuses to build
# because the module has not adopted a proposal would be a page that blocks the decision it exists
# to inform.
OPTIONAL_KEYS = ("wheel_aspect",)

# Reference screens, as CSS pixels of BROWSER VIEWPORT rather than of panel -- which is what the
# fit actually divides by, and is smaller than the panel by whatever the window chrome takes.
#
# The first two were READ OFF THE MACHINES this game is developed on (2026-09-17), browser
# window and devicePixelRatio together, and they replaced estimates that were wrong in a way
# worth recording: the laptop's chrome takes 159 px rather than the 122 that was assumed, and
# the ultrawide reports a pixel ratio of ONE, not two.
#
# That second correction inverts the obvious conclusion, which is why these are in the file
# rather than in someone's memory. The 14-inch laptop draws the wheel into 1204 real pixels;
# the 34-inch ultrawide draws it into 964. The big monitor shows a wheel 60% wider and resolves
# it with a fifth fewer pixels, so the LAPTOP sets the resolution the artwork has to meet and
# the ultrawide never will. Nothing about the layout says that; only the measurement does.
#
# The rest are estimates, and the page labels them as such. They are kept because the question
# this page answers is a comparison, and a comparison against two points is a line.
REFERENCE = [
    {"name": 'MacBook Pro 14"', "vw": 1512, "vh": 823, "dpr": 2.0, "measured": True},
    {"name": '34" ultrawide 21:9', "vw": 3440, "vh": 1318, "dpr": 1.0, "measured": True},
    {"name": 'MacBook Pro 16"', "vw": 1728, "vh": 982, "dpr": 2.0},
    {"name": '27" 1440p', "vw": 2560, "vh": 1305, "dpr": 2.0},
    {"name": '49" super-ultrawide 32:9', "vw": 5120, "vh": 1305, "dpr": 1.0},
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
    keys = LAYOUT_KEYS + tuple(k for k in OPTIONAL_KEYS if k in gv.DEFAULTS)
    L = {k: gv.DEFAULTS[k] for k in keys}
    L.update({k: v for k, v in over.items() if k in keys})
    return L


def best_canvas(L: dict, aspect: float) -> float:
    """The canvas width at which the wheel stops being pinched by width, in closed form.

    Below it the wheel is still growing with the canvas; above it the wheel is fixed and every
    further unit of canvas width is paid for in scale, because the stage is zoom-to-fitted. So
    this is the optimum -- and there is no screen term in it, which is the whole reason one
    canvas can serve every display. The page draws the measured hills beside it; they agree.
    """
    inner_h = L["canvas_height"] - L["margin_top"] - L["margin_bottom"]
    height_term = (inner_h - L["special_height"] - L["banner_height"]) * aspect
    panel_w = L["board_width"] * (gv.FRAME_END - gv.FRAME_START)
    return (height_term + L["board_width"] + panel_w
            + L["column_gap_1"] + L["column_gap_2"] + 2 * gv.STAGE_PAD)


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
#nest,#curve,#peak{display:block;width:100%;height:auto}
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
  <span><i style="background:#c9b27a"></i>pinned or measured</span>
  <span><i style="background:#6b6354"></i>estimated</span>
</div>

<h2>Wheel size against window height</h2>
<svg id="curve" viewBox="0 0 1200 300" preserveAspectRatio="xMinYMin meet"></svg>
<p class="note">Vertical axis is the wheel in px. The line is a <b>ceiling</b>, not a prediction:
any window wider than the canvas aspect sits exactly on it, so its height is the only thing that
moved it. A window <i>narrower</i> than the canvas is width-bound and its dot drops below the line
by however much width it is short &mdash; so the gap between a dot and the line is the entire
value of that screen's width, and on every screen here it is zero.</p>

<h2>One duty tile against canvas width</h2>
<svg id="peak" viewBox="0 0 1200 330" preserveAspectRatio="xMinYMin meet"></svg>
<p class="note" id="peaknote"></p>

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
/* The aspect comes from gen_game_view IF it has one. Today it does not: its wheel is
   square because `wheel` is a single number used as both width and height, so this
   falls back to 1.00 and the page says out loud that anything above it is a proposal.
   Written this way rather than hard-coded so that the day the module grows the
   setting, the page picks it up and stops calling it a proposal by itself. */
if (typeof L.wheel_aspect !== "number") { L.wheel_aspect = 1.0; }
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
  /* A SQUARE component takes min(width, height) and is done. A component of aspect A
     takes width first and spends height at w / A, so the height term becomes
     (main_h - banner_h) * A -- and at A = 1 that is the same expression the module
     has. Which is the point: the landscape branch has to reduce to the square one
     exactly, not approximately, or every number this page has ever shown moves. */
  var A = L.wheel_aspect || 1.0;
  var wheel = Math.max(0, Math.min(wheel_room, (main_h - banner_h) * A));
  var left_top = L.row_gap;
  return {
    inner_w: inner_w, inner_h: inner_h, bw: bw, bh: bh, panel_w: panel_w,
    top_h: top_h, main_h: main_h, banner_h: banner_h,
    wheel_room: wheel_room, wheel: wheel, wheel_h: wheel / A, aspect: A,
    bound_by: wheel_room <= (main_h - banner_h) * A ? "width" : "height",
    left_top: left_top,
    left_h: L.special_activities ? main_h - left_top : inner_h - left_top,
    left_lift: L.special_activities ? 0.0 : top_h,
    boards_h: L.seats * bh + (L.seats - 1) * L.board_gap
  };
}

/* THE BEST CANVAS, IN CLOSED FORM, AND WHY IT IS THE SAME FOR EVERY SCREEN.

   The wheel grows with canvas width only until it becomes height-bound; past that
   it is fixed at (main_h - banner_h) * A and every further unit of canvas width is
   bought with scale, because k falls once the canvas outgrows the display. So the
   optimum is exactly the width at which those two terms meet -- and that width is a
   property of the CANVAS and the ASPECT, with no screen term in it at all.

   Which is the whole answer to "one build or three": the screens cannot disagree
   about this, because the number does not depend on them. The hills drawn below are
   a measurement of the same thing, kept because a formula that agrees with a picture
   is worth more than either alone -- and because they show what it COSTS to be off
   it, which the formula does not. */
function bestCanvas(L){
  var inner_h = L.canvas_height - L.margin_top - L.margin_bottom;
  var height_term = (inner_h - L.special_height - L.banner_height) * (L.wheel_aspect || 1.0);
  var panel_w = L.board_width * (FRAME_END - FRAME_START);
  return height_term + L.board_width + panel_w + L.column_gap_1 + L.column_gap_2 + 2 * STAGE_PAD;
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
  /* devicePixelRatio is carried because it is the one term here that cannot be
     reasoned about from the layout at all. It decides how many real pixels a cell
     is drawn into, and therefore how large the generated artwork has to be -- and
     it is not implied by the viewport: two displays reporting the same CSS size can
     differ by a factor of two in what they actually draw. A reference screen can
     only ASSUME it, which is exactly why pinning a real one is worth doing. */
  var out = [{ name: "This window", vw: window.innerWidth, vh: window.innerHeight,
               dpr: window.devicePixelRatio || 1, live: true }];
  pins.forEach(function (p){
    out.push({ name: p.name, vw: p.vw, vh: p.vh, dpr: p.dpr || 1, pinned: true }); });
  REFERENCE.forEach(function (r){
    // a reference the same size as something already shown is noise
    var dup = out.some(function (o){
      return Math.abs(o.vw - r.vw) < 40 && Math.abs(o.vh - r.vh) < 40; });
    if (!dup) out.push({ name: r.name, vw: r.vw, vh: r.vh, dpr: r.dpr || 1,
                        measured: r.measured, assumed: !r.measured });
  });
  return out;
}

/* --------------------------------------------------------------- rendering */
var esc = function (s){ return String(s).replace(/[&<>"]/g, function (c){
  return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); };
var n0 = function (v){ return Math.round(v).toLocaleString(); };
function colourFor(s){
  return s.live ? "#7d9b52" : (s.pinned || s.measured) ? "#c9b27a" : "#6b6354";
}

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

/* THE CHART THAT SETS THE ART BUDGET. Cell width against canvas width, one line per
   screen. It is not a slope, it is a hill: widening the canvas buys the wheel room
   until the canvas outgrows the screen's own aspect, after which the whole stage is
   fitted by WIDTH and starts shrinking faster than the wheel grows. Where the hills
   peak, and whether they peak in the same place, is the question -- because if they
   do, one canvas serves every display and there is nothing for a second build of the
   artwork to be.

   Cell AREA peaks wherever cell WIDTH does: area is width squared over the aspect,
   and the aspect does not depend on the canvas. So one curve answers both. */
function drawPeak(screens){
  var svg = document.getElementById("peak");
  var W = 1200, H = 330, ML = 62, MR = 232, MT = 14, MB = 34;
  var cMin = 1500, cMax = 2800, step = 10;
  var series = screens.map(function (s){
    var pts = [], best = { px: -1, cw: 0 };
    for (var cw = cMin; cw <= cMax; cw += step) {
      var L2 = {}; for (var k in L) L2[k] = L[k];
      L2.canvas_width = cw;
      var px = geometry(L2).wheel * fitScale(s.vw, s.vh, L2) * CONST.TILE_FRAC;
      pts.push([cw, px]);
      if (px > best.px) best = { px: px, cw: cw };
    }
    return { s: s, pts: pts, best: best };
  });
  var top = Math.max.apply(null, series.map(function (q){ return q.best.px; })) * 1.1 || 1;
  var X = function (v){ return ML + (v - cMin) / (cMax - cMin) * (W - ML - MR); };
  var Y = function (v){ return H - MB - v / top * (H - MT - MB); };
  var p = [];
  p.push('<rect x="' + ML + '" y="' + MT + '" width="' + (W - ML - MR) + '" height="' +
         (H - MT - MB) + '" fill="#17150f" rx="4"/>');
  [0, 0.25, 0.5, 0.75, 1].forEach(function (f){
    p.push('<line x1="' + ML + '" y1="' + Y(top * f).toFixed(1) + '" x2="' + (W - MR) +
           '" y2="' + Y(top * f).toFixed(1) + '" stroke="#3a352a" stroke-width="0.8"/>');
    p.push('<text x="' + (ML - 8) + '" y="' + (Y(top * f) + 4).toFixed(1) + '" text-anchor="end" ' +
           'font-size="11.5" font-family="Georgia,serif" fill="#8d8471">' + n0(top * f) + '</text>');
  });
  // where the canvas is set right now
  p.push('<line x1="' + X(L.canvas_width).toFixed(1) + '" y1="' + MT + '" x2="' +
         X(L.canvas_width).toFixed(1) + '" y2="' + (H - MB) +
         '" stroke="#c9b27a" stroke-width="1.2" stroke-dasharray="5 4"/>');
  p.push('<text x="' + (X(L.canvas_width) + 6).toFixed(1) + '" y="' + (MT + 13) +
         '" font-size="11.5" font-family="Georgia,serif" fill="#c9b27a">canvas ' +
         L.canvas_width + '</text>');
  // and where the arithmetic says the peak is, which should land on every hill's top
  var bc = bestCanvas(L);
  if (bc >= cMin && bc <= cMax) {
    p.push('<line x1="' + X(bc).toFixed(1) + '" y1="' + MT + '" x2="' + X(bc).toFixed(1) +
           '" y2="' + (H - MB) + '" stroke="#8fbf73" stroke-width="1.2"/>');
    p.push('<text x="' + (X(bc) + 6).toFixed(1) + '" y="' + (H - MB - 6).toFixed(1) +
           '" font-size="11.5" font-family="Georgia,serif" fill="#8fbf73">best ' +
           bc.toFixed(0) + '</text>');
  }
  var taken = [];
  series.sort(function (a, b){ return b.best.px - a.best.px; }).forEach(function (q){
    var c = colourFor(q.s);
    p.push('<polyline fill="none" stroke="' + c + '" stroke-width="' + (q.s.live ? 2.2 : 1.5) +
           '" points="' + q.pts.map(function (t){
             return X(t[0]).toFixed(1) + "," + Y(t[1]).toFixed(1); }).join(" ") + '"/>');
    p.push('<circle cx="' + X(q.best.cw).toFixed(1) + '" cy="' + Y(q.best.px).toFixed(1) +
           '" r="3.6" fill="' + c + '"/>');
    var ly = Y(q.best.px) + 4;
    while (taken.some(function (t){ return Math.abs(t - ly) < 15; })) ly += 15;
    taken.push(ly);
    p.push('<text x="' + (W - MR + 10) + '" y="' + ly.toFixed(1) + '" font-size="12" ' +
           'font-family="Georgia,serif" fill="' + c + '">' + esc(q.s.name) + ' &#183; peak ' +
           q.best.cw + ' &#183; ' + n0(q.best.px) + ' px</text>');
  });
  p.push('<text x="' + ML + '" y="' + (H - 8) + '" font-size="11.5" font-family="Georgia,serif" ' +
         'fill="#8d8471">canvas width ' + cMin + '</text>');
  p.push('<text x="' + (W - MR) + '" y="' + (H - 8) + '" text-anchor="end" font-size="11.5" ' +
         'font-family="Georgia,serif" fill="#8d8471">' + cMax + '</text>');
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  svg.innerHTML = p.join("");
  return series;
}

/* THE ART BUDGET, which is the only thing on this page a real measurement can
   settle. One send of the image tool returns about 1.57 Mpx reshaped to whatever
   aspect is asked for, so the source for one cell is fixed by the cell's SHAPE; what
   varies is how many real pixels the screen wants, and that is CSS size times
   devicePixelRatio. Under 1.00x the picture is being drawn larger than it was made
   and will look soft -- which is a decision to take before generating nine of them,
   not after. */
function artStat(cellW, cellH, dpr, s){
  var needW = cellW * dpr, needH = cellH * dpr;
  var A = cellW / Math.max(cellH, 1e-6);
  var sendW = Math.sqrt(CONST.SEND_MPX * A), sendH = sendW / A;
  var ratio = Math.min(sendW / Math.max(needW, 1), sendH / Math.max(needH, 1));
  return '<div class="stat ' + (ratio >= 1 ? 'good' : 'warn') + '"><span>art per cell at ' +
    dpr.toFixed(2) + '&#215;' + (s.assumed ? ' (assumed)' : '') + '</span><b>' +
    n0(needW) + ' &#215; ' + n0(needH) + ' needed, ' + ratio.toFixed(2) + '&#215; from one send' +
    '</b></div>';
}

function card(s, G){
  var dpr = s.dpr || 1;
  var k = fitScale(s.vw, s.vh, L);
  var stageW = L.canvas_width * k, stageH = L.canvas_height * k;
  var wheelPx = G.wheel * k, wheelHPx = G.wheel_h * k;
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
         '" height="' + q(G.wheel_h) + '" fill="#7d9b52" fill-opacity="0.85" rx="2"/>');
  // the nine cells, so a landscape wheel is visibly a 3x3 of landscape cells rather
  // than a green box that happens to be wider
  for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++) {
    var cwu = G.wheel * CONST.TILE_FRAC, chu = G.wheel_h * CONST.TILE_FRAC;
    var gx = (G.wheel - 3 * cwu) / 4, gy = (G.wheel_h - 3 * chu) / 4;
    p.push('<rect x="' + (wx + u(gx + c * (cwu + gx))).toFixed(2) + '" y="' +
           (wy + u(gy + r * (chu + gy))).toFixed(2) + '" width="' + q(cwu) + '" height="' +
           q(chu) + '" fill="#2f3b23" fill-opacity="0.55" rx="0.6"/>');
  }
  // the height the wheel could not reach, which the boxes take
  if (G.main_h - G.banner_h - G.wheel_h > 0.5) {
    p.push('<rect x="' + wx.toFixed(1) + '" y="' + (wy + u(G.wheel_h)).toFixed(1) + '" width="' +
           q(G.wheel) + '" height="' + q(G.main_h - G.banner_h - G.wheel_h) +
           '" fill="#d4695e" fill-opacity="0.35" rx="1"/>');
  }
  p.push('<rect x="' + ox.toFixed(1) + '" y="' + oy.toFixed(1) + '" width="' + sw.toFixed(1) +
         '" height="' + sh.toFixed(1) + '" fill="none" stroke="#a08f68" stroke-width="0.8"/>');
  p.push('<rect x="0.4" y="0.4" width="' + (W - 0.8) + '" height="' + (H - 0.8).toFixed(1) +
         '" fill="none" stroke="' + colourFor(s) + '" stroke-width="1.4" rx="3"/>');

  var tag = s.live ? '<span class="tag">this window</span>'
          : s.pinned ? '<span class="tag">pinned</span>'
          : s.measured ? '<span class="tag">measured</span>'
          : '<span class="tag est">estimate</span>';
  var rm = s.pinned ? ' <button class="drop" data-drop="' + esc(s.name) + '">remove</button>' : '';

  return '<div class="card' + (s.live ? ' me' : '') + '">' +
    '<h3><span>' + esc(s.name) + '</span>' + tag + '</h3>' +
    '<p class="dims">' + s.vw + ' &#215; ' + s.vh + ' css px &#183; ' +
      (s.vw / s.vh).toFixed(2) + ':1 &#183; ' + dpr.toFixed(2) + '&#215;' +
      (s.assumed ? ' assumed' : '') + ' &#183; stage at ' + (k * 100).toFixed(1) + '%' + rm +
      '</p>' +
    '<svg viewBox="0 0 ' + W + ' ' + H.toFixed(1) + '">' + p.join("") + '</svg>' +
    '<div class="stat good"><span>duty wheel</span><b>' + n0(wheelPx) + ' &#215; ' +
      n0(wheelHPx) + ' px</b></div>' +
    '<div class="stat"><span>one duty tile</span><b>' + n0(wheelPx * CONST.TILE_FRAC) +
      ' &#215; ' + n0(wheelHPx * CONST.TILE_FRAC) + ' px</b></div>' +
    '<div class="stat ' + (gutterW > 40 ? 'warn' : '') + '"><span>' +
      (heightBound ? 'width doing nothing' : 'height doing nothing') + '</span><b>' +
      n0(heightBound ? gutterW : gutterH) + ' px</b></div>' +
    artStat(wheelPx * CONST.TILE_FRAC, wheelHPx * CONST.TILE_FRAC, dpr, s) +
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
    '<div><div class="lbl">pixel ratio</div><div class="big">' +
      (window.devicePixelRatio || 1).toFixed(2) + '&#215;</div></div>' +
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
    ' &#215; ' + G.wheel_h.toFixed(1) + '</b> canvas units at aspect <b>' +
    L.wheel_aspect.toFixed(2) + '</b>' +
    (CONST.ASPECT_IS_REAL
      ? ''
      : Math.abs(L.wheel_aspect - 1) < 0.005
        ? ' (square &mdash; the wheel as gen_game_view actually builds it)'
        : ' (a proposal; gen_game_view has no such setting)') +
    ', limited by <b>' + G.bound_by + '</b> &#183; it has ' + G.wheel_room.toFixed(1) +
    ' of width against a height term of ' + ((G.main_h - G.banner_h) * L.wheel_aspect).toFixed(1) +
    ', and takes the smaller. ' +
    (G.bound_by === "height"
      ? 'Widening the canvas will not help until the height term moves &mdash; which is what ' +
        'the aspect does: every 0.1 of it is another ' +
        ((G.main_h - G.banner_h) * 0.1).toFixed(0) + ' units of width the wheel can reach for.'
      : 'It is pinched by width, so a wider canvas &mdash; or a narrower board &mdash; is the lever.');

  document.getElementById("cards").innerHTML =
    screens.map(function (s){ return card(s, G); }).join("");
  drawNest(screens);
  drawCurve(screens, G);
  var series = drawPeak(screens);
  var spread = series.map(function (q){ return q.best.cw; });
  var lo = Math.min.apply(null, spread), hi = Math.max.apply(null, spread);
  var costs = series.map(function (q){
    var L2 = {}; for (var k in L) L2[k] = L[k];
    L2.canvas_width = L.canvas_width;
    var here = geometry(L2).wheel * fitScale(q.s.vw, q.s.vh, L2) * CONST.TILE_FRAC;
    return { name: q.s.name, pct: (1 - (here / q.best.px) * (here / q.best.px)) * 100 };
  });
  document.getElementById("peaknote").innerHTML =
    'The arithmetic puts the best canvas at <b>' + bestCanvas(L).toFixed(0) + '</b> for aspect ' +
    L.wheel_aspect.toFixed(2) + ', and it says so without reference to any screen: the peak is ' +
    'simply where the wheel stops being pinched by width and starts being pinched by height, ' +
    'and that crossing is a fact about the canvas. The measured hills agree &mdash; every ' +
    'screen&rsquo;s own best lies between <b>' + lo + '</b> and <b>' + hi +
    '</b>. At the canvas set above, each one gives up this much CELL AREA against its own best: ' +
    costs.map(function (c){ return esc(c.name) + ' <b>' +
      (c.pct < 0.5 ? "nothing" : "&minus;" + c.pct.toFixed(0) + "%") + '</b>'; }).join(", ") +
    '. A spread this tight is the whole answer to &ldquo;do we need one build per screen&rdquo;: ' +
    'there is no disagreement big enough for a second set of artwork to resolve.';

  document.getElementById("footer").innerHTML =
    'A screen is <b>height-bound</b> whenever it is wider than the canvas aspect of ' +
    (L.canvas_width / L.canvas_height).toFixed(3) + ':1, and every ordinary display is. ' +
    'That is the whole trap: two monitors thousands of pixels apart in width hand the wheel the ' +
    'same number, because both are fitted by their <b>height</b>. Extra width only becomes ' +
    'reachable by changing the canvas aspect, which is what <code>canvas_width</code> does &mdash; ' +
    'drag it and watch the widest card move while the laptop card stands still. ' +
    '<b>And that is only half of it:</b> a square wheel cannot spend width however much it is ' +
    'given, because its height is its width. Drag <code>wheel aspect</code> past 1.00 and the ' +
    'height term opens up &mdash; the wheel becomes the first component in this layout that can ' +
    'turn canvas width into size. The two sliders are one decision, which is why the hills above ' +
    'move when either of them does.';

  wire();
}

function wire(){
  var pinBtn = document.getElementById("pin");
  if (pinBtn) pinBtn.onclick = function (){
    var el = document.getElementById("pinname");
    var name = (el.value || "").trim() || (window.innerWidth > 2200 ? "Wide screen" : "Laptop");
    pins = pins.filter(function (p){ return p.name !== name; });
    pins.push({ name: name, vw: window.innerWidth, vh: window.innerHeight,
                dpr: window.devicePixelRatio || 1 });
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
  { key: "banner_height", label: "banner",        min: 0,    max: 200,  step: 1 },
  // 1.00 is the wheel as it is. Everything above it is the proposal.
  { key: "wheel_aspect",  label: "wheel aspect",  min: 1,    max: 2.2,  step: 0.01 }
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
        # What ONE send of the image tool returns, from the prompts README: about 1.57 Mpx
        # reshaped to whatever aspect is asked for. It is a property of gpt-image-1, not a
        # setting, so it is the ceiling on any per-cell source and the page can say outright
        # whether a screen has outgrown it.
        "SEND_MPX": 1.57e6,
        # Whether the wheel's aspect is a real setting yet, or still the page's proposal. The
        # page's wording follows this rather than being written for today.
        "ASPECT_IS_REAL": "wheel_aspect" in gv.DEFAULTS,
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
    L0 = layout_for({})
    print("  best canvas  %.0f at aspect 1.00 (today's is %s), %.0f at 1.75 -- no screen term"
          % (best_canvas(L0, 1.0), gv.DEFAULTS["canvas_width"], best_canvas(L0, 1.75)))
    for s in REFERENCE:
        k = min(s["vw"] / gv.DEFAULTS["canvas_width"], s["vh"] / gv.DEFAULTS["canvas_height"])
        print("  %-26s %4d x %4d @%.2fx %-10s wheel %4.0f css / %4.0f real px"
              % (s["name"], s["vw"], s["vh"], s.get("dpr", 1),
                 "measured" if s.get("measured") else "estimate",
                 G["wheel"] * k, G["wheel"] * k * s.get("dpr", 1)))
    if args.open:
        import webbrowser
        webbrowser.open(OUT.resolve().as_uri())


if __name__ == "__main__":
    main()
