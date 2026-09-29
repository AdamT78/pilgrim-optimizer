"""Break each Layout Helpers behaviour on purpose and see whether tests A-J notice.

The gap-ordering entry is the bug that was actually in this build: rowGapSuggested() read after
the widths moved rather than before. It is kept as a mutation because that is the one a future
edit is most likely to reintroduce.
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
TMP = OUT / "lab_mut42.html"
BASE = SRC.read_text()

MUTS = [
 # ---- the wheel ------------------------------------------------------------------------------
 ('W.x = Math.round((CANVAS_W - W.width) / 2);\n  syncAttached();\n  commit(soon);',
  'syncAttached();\n  commit(soon);',
  "the helper resize no longer centring the wheel"),
 ('W.height = Math.round(W.width * WHEEL_RATIO);',
  'W.height = Math.round(W.width * 0.6);',
  "the helper resize breaking the 32 degree ratio"),
 ('function setWheelWidth(w, soon){\n  if (!requireUnlocked(needs("resize the wheel", [WHEEL_O()]))) return;\n  var W = S.wheel;',
  'function setWheelWidth(w, soon){\n  if (!requireUnlocked(needs("resize the wheel", [WHEEL_O()]))) return;\n  var W = S.wheel;\n  W.y = 500;',
  "the helper resize moving the wheel's y"),
 ('''function centreWheelX(){
  if (!requireUnlocked(needs("centre the wheel", [WHEEL_O()]))) return;
  S.wheel.x = Math.round((CANVAS_W - S.wheel.width) / 2);''',
  '''function centreWheelX(){
  if (!requireUnlocked(needs("centre the wheel", [WHEEL_O()]))) return;
  S.wheel.width = 1372;
  S.wheel.x = Math.round((CANVAS_W - S.wheel.width) / 2);''',
  "centre wheel x also resetting the width"),
 ('W.x = Math.round((CANVAS_W - W.width) / 2);\n  syncAttached();',
  'W.x = Math.round((CANVAS_W - W.width) / 2);',
  "the acolytes left behind by a wheel resize"),
 # ---- the duty cards --------------------------------------------------------------------------
 ('DUTY_ORDER.forEach(function(s){ S.duties[s].card.height = v; });',
  'S.duties[DUTY_ORDER[0]].card.height = v;',
  "the group height reaching only the first card"),
 ('''function setCardHeights(h, soon){
  if (!requireUnlocked(needs("resize the duty cards", ALL_CARDS()))) return;
  var v = clamp(Math.round(h), HELPERS.cardH[0], HELPERS.cardH[1]);
  DUTY_ORDER.forEach(function(s){ S.duties[s].card.height = v; });''',
  '''function setCardHeights(h, soon){
  if (!requireUnlocked(needs("resize the duty cards", ALL_CARDS()))) return;
  var v = clamp(Math.round(h), HELPERS.cardH[0], HELPERS.cardH[1]);
  DUTY_ORDER.forEach(function(s){ S.duties[s].card.height = v; });
  artOf("left").y = 78 + v + 12; artOf("right").y = artOf("left").y;
  S.tithe.y = artOf("left").y; S.city.y = artOf("left").y;''',
  "taller cards pushing the action row down"),
 ('''  var y = S.duties[DUTY_ORDER[0]].card.y;
  DUTY_ORDER.forEach(function(s){ S.duties[s].card.y = y; });''',
  '''  var y = S.duties[DUTY_ORDER[0]].card.y;
  DUTY_ORDER.forEach(function(s){ S.duties[s].card.y = y; S.duties[s].card.height = 150; });''',
  "align card tops also resetting the heights"),
 # ---- the artwork ------------------------------------------------------------------------------
 ('''  var gap = rowGapSuggested();
  artOf("left").width = v; artOf("right").width = v;
  layoutActionRow(gap);''',
  '''  artOf("left").width = v; artOf("right").width = v;
  layoutActionRow(rowGapSuggested());''',
  "the gap read after the widths move, not before"),
 ('''  L.height = v; R.height = v;
  R.y = L.y;''',
  '''  L.height = v; R.height = v;
  R.y = L.y;
  S.tithe.height = v; S.city.height = v;''',
  "linked artwork height dragging Tithe and the City with it"),
 ('''  L.height = v; R.height = v;
  R.y = L.y;''',
  '''  L.height = v; R.height = v;''',
  "the two artwork boxes left at different y"),
 ('  artOf("left").width = v; artOf("right").width = v;',
  '  artOf("right").width = v;',
  "the linked width reaching only one box"),
 # ---- the row ------------------------------------------------------------------------------------
 ('''  R.x = Math.round(L.x + L.width + gap);
  T.x = Math.round(R.x + R.width + gap);
  C.x = Math.round(T.x + T.width + gap);''',
  '''  L.x = Math.round(L.x + gap);
  R.x = Math.round(L.x + L.width + gap);
  T.x = Math.round(R.x + R.width + gap);
  C.x = Math.round(T.x + T.width + gap);''',
  "the row's left anchor drifting on every change"),
 ('''  var y = artOf("left").y;
  artOf("right").y = y; S.tithe.y = y; S.city.y = y;''',
  '''  var y = artOf("left").y;
  artOf("right").y = y; S.tithe.y = y;''',
  "align row top missing the City"),
 ('var available = CANVAS_W - L.x - HELPERS.rowRight - T.width - C.width - 3 * gap;',
  'var available = CANVAS_W - L.x - HELPERS.rowRight - T.width - C.width - gap;',
  "fit action row counting one gap instead of three"),
 # ---- the readings ---------------------------------------------------------------------------------
 ('''function rowGapCommon(){
  var g = rowGaps();
  return (g[0] === g[1] && g[1] === g[2]) ? g[0] : null;
}''',
  '''function rowGapCommon(){
  return rowGaps()[0];
}''',
  "mixed gaps reported as if they agreed"),
 ('''  var h = '<div class=met>'
        + row("duty cards", spreadText(cg.w) + " × " + spreadText(cg.h)
              + (mixedCards ? " mixed" : " each"), mixedCards ? "mix" : "")''',
  '''  var h = '<div class=met>'
        + row("duty cards", cg.w.lo + " × " + cg.h.lo + " each", "")''',
  "one card reported as if it spoke for eight"),
 ('var gaps = rowGaps(), common = rowGapCommon(), v = cardsToRowGap();',
  'var gaps = rowGaps(), common = rowGapCommon(), v = 99;',
  "the cards-to-row overlap never reported"),
 ('Math.min.apply(null, gaps) < 0 ? "bad" : common !== null ? "" : "mix")',
  'common !== null ? "" : "mix")',
  "an overlapping action gap shown as merely uneven"),
 ('''function rowGapSuggested(){
  var c = rowGapCommon();
  if (c !== null) return c;''',
  '''function rowGapSuggested(){
  var c = rowGapCommon();
  if (c !== null) return 0;''',
  "the gap slider opening at something other than the common value"),
 # ---- history ----------------------------------------------------------------------------------------
 ('      apply(v, true);', '      apply(v, false);',
  "every step of a slider sweep becoming its own undo entry"),
]

run = MutationRun("V4.2 page mutations vs accept42", total=len(MUTS))
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
    r = subprocess.run([shutil.which("node"), str(HERE / "accept42.mjs"), TMP.as_uri()],
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
