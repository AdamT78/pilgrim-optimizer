"""Structured renderer for the v2 duty wheel debug view.

v2 is the oval wheel: a hub and eight spokes on a true ellipse, mirrored about both axes. It does
NOT replace `render_duty_wheel.py`, which still draws the circular board the game uses today.

This is a debug/visual tool only. It reads `duty_wheel_v2_layout.json` for geometry and knows
nothing about `GameState` or the rules.

WHICH WAY ROUND THIS ONE GOES

Everywhere else in this folder the baseline came first -- drawn by hand, committed, and then
reverse-engineered into a layout JSON that a renderer was measured against. This one runs the
other way: `build_duty_wheel_v2.py` computes the geometry, this renderer draws it, and
`prototypes/duty_wheel_v2.html` is that drawing committed. So the prototype here is this
renderer's OUTPUT and not a reference it has to match pixel for pixel. The wax seals are the
same case and the README says so for both.

The practical difference: if you want the wheel to change, change a constant in
`build_duty_wheel_v2.py` and re-run it. Editing the prototype HTML by hand achieves nothing,
because the next run overwrites it.

The nine faces are named by POSITION, not by duty. Duty tiles are shuffled at setup, so which
duty stands on which face is an arrangement and not a fact -- `gen_duty_grid.DUTY_NAMES` makes
the same point about its own list. `index` is the 0..8 grid square, top-left to bottom-right,
which is the order `gen_duty_grid`'s `cells=` argument speaks.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

LAYOUT_PATH = Path(__file__).resolve().parent / "duty_wheel_v2_layout.json"

# Where a face's label sits, as a fraction of the box. Labels are a debug aid; they are not in
# the layout JSON because they say nothing about the shapes.
LABEL_AT = {
    "north_west": (0.22, 0.24), "north": (0.50, 0.14), "north_east": (0.78, 0.24),
    "west": (0.14, 0.50), "centre": (0.50, 0.50), "east": (0.86, 0.50),
    "south_west": (0.22, 0.76), "south": (0.50, 0.86), "south_east": (0.78, 0.76),
}


def load_duty_wheel_v2_layout(path: Path | None = None) -> dict:
    p = LAYOUT_PATH if path is None else Path(path)
    if not p.is_file():
        raise SystemExit(
            "%s is missing. Run `python3 tools/ui_debug/build_duty_wheel_v2.py` to write it; it "
            "carries the nine outlines and there is no wheel without them." % p)
    return json.loads(p.read_text(encoding="utf-8"))


def render_duty_wheel_v2_svg(layout: dict, *, labels: bool = False,
                             standalone: bool = False) -> str:
    """The nine faces. The frame is the CHANNEL between them, not a stroke, so nothing is
    stroked and the ground shows through."""
    w, h = layout["box"], layout["box_h"]
    pal = layout["palette"]
    out = []
    if standalone:
        out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g" '
               'width="%g" height="%g" role="img" aria-label="%s">'
               % (w, h, w, h, escape(layout["title"])))
    out.append('<title>%s</title>' % escape(layout["title"]))
    out.append('<rect id="ground" x="0" y="0" width="%g" height="%g" fill="%s"/>'
               % (w, h, pal["ground"]))
    out.append('<g id="faces" stroke="none">')
    for cell in layout["cells"]:
        fill = pal["centre"] if cell["position"] == "centre" else pal["face"]
        out.append('<path id="%s" data-index="%d" fill="%s" d="%s"/>'
                   % (cell["position"], cell["index"], fill, cell["d"]))
    out.append('</g>')
    if labels:
        out.append('<g id="labels" font-family="Georgia,serif" font-size="19" '
                   'text-anchor="middle" fill="%s">' % pal["label"])
        for cell in layout["cells"]:
            fx, fy = LABEL_AT[cell["position"]]
            out.append('<text x="%.1f" y="%.1f">%d &#183; %s</text>'
                       % (fx * w, fy * h + 6, cell["index"],
                          escape(cell["position"].replace("_", " "))))
        out.append('</g>')
    e = layout["ellipse"]
    out.append('<ellipse id="guide" cx="%g" cy="%g" rx="%g" ry="%g" fill="none" '
               'stroke="#c8402a" stroke-width="1" stroke-dasharray="6 6" display="none"/>'
               % (e["cx"], e["cy"], e["rx"], e["ry"]))
    out.append('</svg>')
    return "\n".join(out) + "\n"


def _checks_table(layout: dict) -> str:
    c = layout["checks"]
    rows = [
        ("frame between faces", "%.2f to %.2f units" % tuple(c["frame_between_faces"]),
         "target %.2f" % layout["frame"]["between_faces"]),
        ("frame around the centre", "%.2f to %.2f units" % tuple(c["frame_around_centre"]),
         "target %.2f" % layout["frame"]["around_centre"]),
        ("mirrored pairs", "%.4f units" % c["mirror_error"],
         "five faces that are a flip of another"),
        ("faces that are their own mirror", "%.4f units" % c["self_mirror_error"],
         "north, south, east, west, centre"),
        ("everything inside the ellipse", "%.4f" % c["max_radial_in_ellipse"],
         "1.0 would be touching it"),
        ("ring face areas", "within %.1f%%" % c["ring_area_spread_pct"],
         "equal 45&#176; steps make equal sector area"),
        ("longest straight run on the centre", "%.1f units" % c["centre_longest_straight_run"],
         "a plain circle its size measures about 17"),
    ]
    return "\n".join(
        '<tr><th>%s</th><td>%s</td><td>%s</td></tr>' % r for r in rows)


def render_duty_wheel_v2_html(layout: dict) -> str:
    cells = "\n".join(
        '<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (c["index"], c["position"].replace("_", " "), "%.0f" % c["area"],
           _origin(layout, c["position"]))
        for c in layout["cells"])
    return PAGE % {
        "title": escape(layout["title"]),
        "source": escape(layout["source"]),
        "aspect": layout["aspect"],
        "aspect_open": escape(layout["aspect_is_open"]),
        "box": layout["box"],
        "box_h": layout["box_h"],
        "svg": render_duty_wheel_v2_svg(layout, labels=True),
        "checks": _checks_table(layout),
        "cells": cells,
        "ground": layout["palette"]["ground"],
        "rule": layout["palette"]["rule"],
    }


def _origin(layout: dict, position: str) -> str:
    if position in layout["drawn"]:
        return "drawn"
    m = layout["mirrors"][position]
    return "%s flipped, %s axis" % (m["of"].replace("_", " "), m["axis"])


PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PILGRIM &mdash; %(title)s</title>
<style>
 :root{color-scheme:light}
 body{margin:0;background:#efe9dc;color:#2a2116;
      font:16px/1.55 Georgia,"Iowan Old Style",serif}
 main{max-width:1060px;margin:0 auto;padding:36px 22px 72px}
 h1{font-size:30px;margin:0 0 2px;letter-spacing:.02em}
 h2{font-size:19px;margin:38px 0 10px;font-weight:600}
 p{margin:0 0 14px;max-width:62em}
 .lede{color:#5d5241}
 figure{margin:22px 0;background:%(ground)s;border-radius:3px;overflow:hidden}
 figure svg{display:block;width:100%%;height:auto}
 table{border-collapse:collapse;margin:6px 0 18px;font-size:15px}
 th,td{text-align:left;padding:5px 18px 5px 0;border-bottom:1px solid #d8cfba;
       vertical-align:top}
 th{font-weight:600;white-space:nowrap}
 td:first-child{font-variant-numeric:tabular-nums}
 .note{border-left:3px solid %(rule)s;padding:2px 0 2px 14px;color:#5d5241;
       margin:18px 0;max-width:58em}
</style>
<main>
<h1>PILGRIM &mdash; %(title)s</h1>
<p class="lede">Debug baseline. Not connected to the game; draws no rules.</p>

<figure>%(svg)s</figure>

<p>%(source)s</p>

<div class="note">This page is its renderer&rsquo;s committed output, not a hand-drawn baseline
the renderer is measured against. To change the wheel, change a constant in
<code>build_duty_wheel_v2.py</code> and re-run it &mdash; editing this file achieves nothing,
because the next run overwrites it.</div>

<h2>What it is drawn to</h2>
<table>%(checks)s</table>

<h2>The nine faces</h2>
<p>Named by position, never by duty: duty tiles are shuffled at setup, so which duty stands on
which face is an arrangement and not a fact. The index is the 0&ndash;8 grid square, top-left to
bottom-right, which is the order <code>gen_duty_grid</code>&rsquo;s <code>cells=</code> speaks.
Only four faces are drawn; the other five are flips, which is why the mirror error above is a
zero and not a small number.</p>
<table>
<tr><th>index</th><th>position</th><th>area, units&sup2;</th><th>origin</th></tr>
%(cells)s
</table>

<h2>The aspect is still open</h2>
<p>The wheel is %(box)g &#215; %(box_h)g units, an aspect of %(aspect)g. %(aspect_open)s</p>
</main>
</html>
"""
