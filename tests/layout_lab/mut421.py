"""Break each V4.2.1 behaviour on purpose and see whether accept421 notices.

Three fixes are under test here: the centralised lock guard, syncHelperInputs(), and FIT ACTION
ROW clamping the gap. The "cannot undefined" entry is the bug that was actually in this build --
the verb read off `stuck` rather than off `needed` -- and every test passed anyway, because they
checked for the lock and the object name instead of reading the sentence. It is kept as a
mutation because a future edit to the message is exactly what would reintroduce it.
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
TMP = OUT / "lab_mut421.html"
BASE = SRC.read_text()

MUTS = [
 # ---- 1. the guard itself -----------------------------------------------------------------
 ('''  if (!stuck.length) return true;''',
  '''  if (!stuck.length) return true;
  return true;''',
  "the lock guard never refusing anything"),

 ('''  needed.forEach(function(o){
    if (lockedOf(o.kind, o.id)) stuck.push(o.label);
  });''',
  '''  [needed[0]].forEach(function(o){
    if (lockedOf(o.kind, o.id)) stuck.push(o.label);
  });''',
  "the guard checking only the first object of the set"),

 ('say("cannot " + needed.verb + " · "',
  'say("cannot " + stuck.verb + " · "',
  "the verb read off the wrong array (the real bug: 'cannot undefined')"),

 ('''        ? " are locked" : " is locked"), true);
  return false;''',
  '''        ? " are locked" : " is locked"), true);
  commit();
  return false;''',
  "a refusal still writing a history entry"),

 ('function needs(verb, list){ list.verb = verb; return list; }',
  'function needs(verb, list){ return list; }',
  "the verb never attached to the set"),

 # ---- 2. which objects each operation declares ---------------------------------------------
 ('if (!requireUnlocked(needs("resize the duty cards", ALL_CARDS()))) return;',
  'if (!requireUnlocked(needs("resize the duty cards", [ALL_CARDS()[0]]))) return;',
  "the group height guarded by Clerical alone"),

 ('''  if (!requireUnlocked(needs("align the duty cards", ALL_CARDS()))) return;''',
  '''  if (!requireUnlocked(needs("align the duty cards", ALL_CARDS().slice(1)))) return;''',
  "align card tops ignoring the anchor card's own lock"),

 ('''  if (!requireUnlocked(needs("resize the action artwork",
                             [ART_L(), ART_R(), TITHE_O(), CITY_O()]))) return;
  var v = clamp(Math.round(w), HELPERS.artW[0], HELPERS.artW[1]);''',
  '''  if (!requireUnlocked(needs("resize the action artwork", [ART_L(), ART_R()]))) return;
  var v = clamp(Math.round(w), HELPERS.artW[0], HELPERS.artW[1]);''',
  "the linked width forgetting it re-lays Tithe and the City"),

 ('if (!requireUnlocked(needs("resize the action artwork", [ART_L(), ART_R()]))) return;\n  var v = clamp(Math.round(h), HELPERS.artH[0], HELPERS.artH[1]);',
  'if (!requireUnlocked(needs("resize the action artwork",\n                             [ART_L(), ART_R(), TITHE_O(), CITY_O()]))) return;\n  var v = clamp(Math.round(h), HELPERS.artH[0], HELPERS.artH[1]);',
  "the linked HEIGHT refusing over Tithe and the City, which it never writes"),

 ('''  if (!requireUnlocked(needs("re-space the action row",
                             [ART_R(), TITHE_O(), CITY_O()]))) return;
  layoutActionRow''',
  '''  if (!requireUnlocked(needs("re-space the action row",
                             [ART_L(), ART_R(), TITHE_O(), CITY_O()]))) return;
  layoutActionRow''',
  "the row gap refusing over the anchor it does not move"),

 ('if (!requireUnlocked(needs("centre the wheel", [WHEEL_O()]))) return;',
  '',
  "centre wheel x losing its guard entirely"),

 ('''function setWheelWidth(w, soon){
  if (!requireUnlocked(needs("resize the wheel", [WHEEL_O()]))) return;''',
  '''function setWheelWidth(w, soon){''',
  "the wheel scale losing its guard entirely"),

 ('function ALL_CARDS(){\n  return DUTY_ORDER.map(function(s){\n    return {kind: "card", id: s, label: S.duties[s].name + "\'s card"};',
  'function ALL_CARDS(){\n  return DUTY_ORDER.map(function(s){\n    return {kind: "duty", id: s, label: S.duties[s].name + "\'s card"};',
  "the card descriptors naming a kind lockedOf() cannot resolve"),

 # ---- 3. syncHelperInputs ------------------------------------------------------------------
 ('  paintMetrics();\n  syncHelperInputs();',
  '  paintMetrics();',
  "the helper controls never re-synced from render"),

 # Anchored on the line above it: syncTokenInputs() guards its own controls the same way,
 # so the bare line matches twice and says nothing about which sync the failure is in.
 ('''    var e = el(id);
    if (!e || e === document.activeElement) return;''',
  '''    var e = el(id);
    if (!e) return;''',
  "the helper sync stamping on the box the caret is in"),

 ('  set("hpCardN", cg.h.lo);         set("hpCardR", cg.h.lo);',
  '  set("hpCardN", cg.h.hi);         set("hpCardR", cg.h.hi);',
  "the card control showing the tallest card rather than the group value"),

 ('  var gp = helperGap();\n  set("hpGapN", gp);               set("hpGapR", gp);',
  '  var gp = rowGapSuggested();\n  set("hpGapN", gp);               set("hpGapR", gp);',
  "the gap control showing a value outside its own range"),

 ('      var actual = read();\n      r.value = actual;',
  '      var actual = v;\n      r.value = actual;',
  "the control echoing what was typed instead of reading the geometry back"),

 ('  set("hpArtWN", L.width);         set("hpArtWR", L.width);',
  '',
  "the artwork width control never re-synced"),

 ('  set("hpWheelN", S.wheel.width);  set("hpWheelR", S.wheel.width);',
  '',
  "the wheel control never re-synced"),

 ('function syncHelperInputs(){\n  if (!el("hpWheelN")) return;',
  'function syncHelperInputs(){\n  if (!el("hpWheelN")) return;\n  buildPanel();',
  "the sync rebuilding the panel instead of writing values into it"),

 # ---- 4. FIT ACTION ROW clamping -----------------------------------------------------------
 ('  var raw = rowGapSuggested();\n  var gap = clamp(raw, HELPERS.gap[0], HELPERS.gap[1]);',
  '  var raw = rowGapSuggested();\n  var gap = raw;',
  "the fit rebuilding the row at whatever gap it found, overlap included"),

 ('  var gap = clamp(raw, HELPERS.gap[0], HELPERS.gap[1]);\n  var available',
  '  var gap = clamp(raw, -200, HELPERS.gap[1]);\n  var available',
  "the fit clamped to a floor that still admits an overlap"),

 ('      + (raw !== gap ? " · normalised from " + raw',
  '      + (false ? " · normalised from " + raw',
  "the fit silently normalising without saying so"),

 # The ordinary resize must NOT gain the fit's clamp: it preserves the composition in progress.
 ('''  var gap = rowGapSuggested();
  artOf("left").width = v; artOf("right").width = v;''',
  '''  var gap = clamp(rowGapSuggested(), HELPERS.gap[0], HELPERS.gap[1]);
  artOf("left").width = v; artOf("right").width = v;''',
  "the ordinary resize quietly repairing a gap the person is mid-experiment on"),

 # ---- 5. V4.2 behaviour that must survive the patch -----------------------------------------
 ('''  var gap = rowGapSuggested();
  artOf("left").width = v; artOf("right").width = v;
  layoutActionRow(gap);''',
  '''  artOf("left").width = v; artOf("right").width = v;
  layoutActionRow(rowGapSuggested());''',
  "the gap read after the widths move, not before (the V4.2 bug)"),
]

run = MutationRun("V4.2.1 page mutations vs accept421", total=len(MUTS))
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
    r = subprocess.run([shutil.which("node"), str(HERE / "accept421.mjs"), TMP.as_uri()],
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
