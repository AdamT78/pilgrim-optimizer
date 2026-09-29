"""Break the V4 page on purpose, one rule at a time, and see whether accept4.mjs notices.

A suite that has never failed is a suite nobody has tested. Each entry below is a change the
brief forbids; a MISSED line is a hole in the acceptance run, not a pass.
"""
import os
import pathlib
import re
import shutil
import subprocess

from mutation_tools import MutationRun, MutationTargetError, replace_exactly_once

# Paths are derived from this file so the suite runs from any checkout. LAYOUT_LAB_OUT points at
# the directory holding the built page; the browser can be moved with LAYOUT_LAB_CHROMIUM.
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = pathlib.Path(os.environ.get("LAYOUT_LAB_OUT", ROOT / "out"))

SRC = OUT / "lab.html"
TMP = OUT / "lab_mut.html"
BASE = SRC.read_text()

# SOME ENTRIES ARE MARKED BENIGN (a fourth element). Those are changes that USED to be defects
# and are now repaired at load time by the wheel-ratio normalisation, so the page absorbs them:
# a stored height, ratio or ratioSource that disagrees with the design invariant is overwritten
# on the way in rather than obeyed. They are kept because a NO-OP turning back into a MISS is
# exactly how that normalisation would be lost.
MUTS = [
 # ---- the wheel is the same object in all three states -------------------------------------
 ('function setView(v){\n  if (!VIEW_STATES.some(function(x){ return x.key === v; })) return;\n  S.view = v;',
  'function setView(v){\n  if (!VIEW_STATES.some(function(x){ return x.key === v; })) return;\n  S.view = v;\n  S.wheel.y = v === "action" ? 430 : 438;',
  "the wheel shifts between states"),
 ('"width": 1372,\n  "height": 727,', '"width": 1372,\n  "height": 620,',
  "a stored height that disagrees with the ratio (repaired on load)", True),
 ('"naturalRatio": 0.5298999999999999,', '"naturalRatio": 0.5624,',
  "a stored ratio from another projection (repaired on load)", True),
 ('"ratioSource": "builtin",', '"ratioSource": "elevation",',
  "a stored ratioSource of anything else (repaired on load)", True),
 ('#wheelObj.noground [id="ground"]{display:none}',
  '#wheelObj.nogroundx [id="ground"]{display:none}',
  "the asset's ground rectangle left showing"),
 ('"x": 14,\n  "y": 438,', '"x": 14,\n  "y": 470,',
  "the wheel pushed down, leaving a gap under it"),
 (r'id=\"north_west\" data-index=\"0\" fill=\"#3a3d45\"',
  r'id=\"north_west\" data-index=\"0\" fill=\"#efe3c8\"',
  "one face left in the builder's parchment"),
 (r'id=\"centre\" data-index=\"4\" fill=\"#23262b\"',
  r'id=\"centre\" data-index=\"4\" fill=\"#3a3d45\"',
  "the hub given the same grey as the faces"),
 ('"colour": "#e8c877"', '"colour": "#3f4148"',
  "a highlight colour that cannot be told from the face"),
 # ---- three states, one message each ---------------------------------------------------------
 ('return String(b.main || "").replace("{n}", S.inHand.count);',
  'return String(b.main || "");', "{n} left in the sow line as literal text"),
 # ---- the artwork is conditional --------------------------------------------------------------
 ('if (kind === "art")   return shownDuty() ? ["ready", "sow", "action"] : [];',
  'if (kind === "art")   return ["ready", "sow", "action"];',
  "artwork on screen before anybody asked for a duty"),
 ('if (kind === "tithe") return ["action"];',
  'if (kind === "tithe") return ["ready", "sow", "action"];',
  "Tithe offered while still sowing"),
 # ---- a preview is not a choice ----------------------------------------------------------------
 ('var cls = "art " + e.fit + (isPreview ? "" : " choice");',
  'var cls = "art " + e.fit + " choice";', "a preview dressed as a choice"),
 ('      if (isPreview){\n        var pv = document.createElement("span");',
  '      if (false){\n        var pv = document.createElement("span");',
  "the PREVIEW badge removed"),
 ('function shownDuty(){\n  if (S.view === "action") return reachedDuty();',
  'function shownDuty(){\n  if (S.view === "action") return S.previewDuty || reachedDuty();',
  "a stale preview survives into ACTION SELECTION"),
 ('function togglePreview(slug){\n  if (S.view === "action") return;\n  S.previewDuty = (S.previewDuty === slug) ? null : slug;',
  'function togglePreview(slug){\n  if (S.view === "action") return;\n  S.previewDuty = slug;',
  "a preview that will not close"),
 # ---- the reached-duty highlight ------------------------------------------------------------------
 ('.hl{position:absolute;pointer-events:none;z-index:22}',
  '.hl{position:absolute;pointer-events:none;z-index:19}',
  "the highlight back underneath the wheel"),
 ('  if (S.view === "action" && H.visible){',
  '  if (H.visible){', "a duty highlighted before anything reached it"),
 # ---- nothing identifies a duty space on the wheel -------------------------------------------------
 ("                '<span class=nm>wheel</span>' + wheelInner, WHEEL_Z);",
  "                '<span class=nm>wheel</span>' + wheelInner"
  " + '<div style=\"position:absolute;left:40%;top:8%\">CLERICAL</div>', WHEEL_Z);",
  "a duty named on the wheel"),
 # ---- the ribbon ------------------------------------------------------------------------------------
 ('"x": 1212,\n    "y": 78,\n    "width": 159,', '"x": 1212,\n    "y": 78,\n    "width": 260,',
  "the last card widened until the row leaves the module"),
 ('DUTY_ORDER.forEach(function(slug){\n    var D = S.duties[slug], cd = D.card;',
  'DUTY_ORDER.slice().sort().forEach(function(slug){\n    var D = S.duties[slug], cd = D.card;',
  "cards alphabetised instead of following the wheel"),
 # ---- the action band -------------------------------------------------------------------------------
 ('"x": 803,', '"x": 700,', "Tithe overlapping the right-hand artwork"),
 # ---- the acolyte ring against the real faces ------------------------------------------------------------
 ('"x": 1228,\n    "y": 802,\n    "u": 0.8848,', '"x": 1370,\n    "y": 802,\n    "u": 0.9884,',
  "one duty's row pushed out over the rim"),
 # give_alms opens with four figures, so it is the row whose ends are furthest from its anchor.
 ('"x": 327,\n    "y": 976,\n    "u": 0.2279,\n    "v": 0.7402,\n    "count": 4,\n    "spacing": 74,',
  '"x": 327,\n    "y": 976,\n    "u": 0.2279,\n    "v": 0.7402,\n    "count": 4,\n    "spacing": 210,',
  "a row widened until its ends leave its own face"),
 # ---- the City is two jobs in one region --------------------------------------------------------------
 ('var c = S.city, hand = (S.view === "sow");', 'var c = S.city, hand = false;',
  "the in-hand pool never appears"),
 # ---- the exports -------------------------------------------------------------------------------------
 ('      d[a.key] = {name: act.name, shortLabel: act.shortLabel};',
  '      d[a.key] = {name: act.name, shortLabel: act.shortLabel, scenic: act.scenic,\n'
  '                  x: 0, y: 0, width: 375, height: 184};',
  "sixteen boxes back in the game layout"),
 ('  var out = {\n    version: STATE_VERSION,',
  '  var out = clone(S); out.version = STATE_VERSION; var unused = {\n    version: STATE_VERSION,',
  "a subtractive game layout that leaks the editor"),
 # ---- migration ------------------------------------------------------------------------------------------
 ('        delete D.figures.u; delete D.figures.v;',
  '        ;',
  "V3 u/v kept, so the acolyte ring is re-derived at the wrong scale"),
 ('        D.figures.x = def.duties[s].figures.x;\n        D.figures.y = def.duties[s].figures.y;',
  '        ;',
  "the V3 acolyte ring reused at the V4 wheel's size"),
 ('  S.view = v;\n  S.previewDuty = null;', '  S.view = v;',
  "an open preview carried into the next state"),
 # The pool is what keeps bytes out of the state, so the mutation that matters is the one that
 # bypasses it -- stripDataUrls alone is belt-and-braces and removing it changes nothing.
 ('function putImage(url){ var k = "im" + (++IMG_SEQ); IMAGES[k] = url; return k; }',
  'function putImage(url){ var k = "im" + (++IMG_SEQ); IMAGES[k] = url; return url; }',
  "the image pool bypassed, bytes put straight into the state"),
 ('    ["wheel", "status", "city", "tithe"].forEach(function(k){',
  '    [].forEach(function(k){',
  "V3 geometry carried across the V4 boundary"),
 ('      delete D.label;', '      ;', "the retired duty label kept alive"),
 # ---- persistence ----------------------------------------------------------------------------------------
 # ---- undo ------------------------------------------------------------------------------------------------
 ('function setFull(on){\n  document.body.classList.toggle("full", !!on);',
  'function setFull(on){\n  document.body.classList.toggle("full", false);',
  "full screen that never engages"),
 ('function setZoom(z){ S.zoom = z; relayout(); save(true); }',
  'function setZoom(z){ S.zoom = "fit"; relayout(); save(true); }',
  "the zoom steps all collapsing to FIT"),
]

run = MutationRun("V4 page mutations vs accept4", total=len(MUTS))
for entry in MUTS:
    old, new, label = entry[0], entry[1], entry[2]
    benign = len(entry) > 3 and entry[3]
    try:
        mutated = replace_exactly_once(BASE, old, new, label)
    except MutationTargetError as err:
        # NOT a skip. A target that no longer resolves has stopped testing anything, and the run
        # is red on that alone -- see mutation_tools.py.
        run.record_invalid(label, err)
        continue
    TMP.write_text(mutated)
    r = subprocess.run([shutil.which("node"), str(HERE / "accept4.mjs"), TMP.as_uri()],
                       capture_output=True, text=True, cwd=str(ROOT))
    out = (r.stdout + r.stderr).strip().splitlines()
    fails = [x for x in out if x.startswith("FAIL")]
    # A finished run always prints "<n>/<m> passed". Its absence means the harness threw and
    # never reached its own summary, so nothing in it actually judged this mutation.
    crashed = not any(re.search(r"\d+/\d+ passed", ln) for ln in out)
    run.record(label, r.returncode != 0, out[-1] if out else "(no output)", fails[:2], benign,
               crashed)

TMP.unlink(missing_ok=True)
raise SystemExit(run.report())
