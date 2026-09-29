"""Break each duty-art behaviour on purpose and see whether accept43 notices."""
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mutation_tools import MutationRun, MutationTargetError, replace_exactly_once

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = pathlib.Path(os.environ.get("LAYOUT_LAB_OUT", ROOT / "out"))
SRC = OUT / "lab.html"
TMP = OUT / "lab_mut43.html"
BASE = SRC.read_text()

MUTS = [
 # ---- ownership: the action owns the art, not the slot -------------------------------------
 ('''      var act = S.duties[slug][key];
      act.scenic = imgKey;
      act.scenicName = name;''',
  '''      var act = S.duties[slug][key === "actionA" ? "actionB" : "actionA"];
      act.scenic = imgKey;
      act.scenicName = name;''',
  "the pair loaded into the wrong actions (reversed)"),
 ('''      var act = S.duties[slug][key];
      act.scenic = imgKey;''',
  '''      var act = S.duties[slug][key];
      S.duties[slug][key === "actionA" ? "leftImage" : "rightImage"] = imgKey;
      act.scenic = imgKey;''',
  "artwork identity attached to a screen side"),
 ('act.scenic = imgKey;\n      act.scenicName = name;',
  'act.scenic = imgSrc(imgKey);\n      act.scenicName = name;',
  "image bytes written straight into the state instead of a pool key"),

 # ---- partial import and clearing ----------------------------------------------------------
 ('  ACTIONS.forEach(function(a){ if (pairPick[a.key]) chosen.push(a.key); });',
  '  ACTIONS.forEach(function(a){ chosen.push(a.key); });',
  "an empty file field treated as a choice"),
 ('''function clearActionArt(key){
  var D = S.duties[artPairDuty], act = D && D[key];''',
  '''function clearActionArt(key){
  var D = S.duties[artPairDuty], act = D && D.actionA;''',
  "clear always clearing Action A whichever button was pressed"),
 ('''  act.scenic = null;
  act.scenicName = null;
  commitPanels();''',
  '''  act.scenic = null;
  act.scenicName = null;
  D.actionA.scenic = null; D.actionA.scenicName = null;
  D.actionB.scenic = null; D.actionB.scenicName = null;
  commitPanels();''',
  "clear taking both actions with it"),

 # ---- history ------------------------------------------------------------------------------
 ('      if (pending === 0) finishDutyArtPair(slug, loaded);',
  '      finishDutyArtPair(slug, loaded);',
  "a two-file load becoming two undo entries"),

 # ---- auto-preview -------------------------------------------------------------------------
 ('''  if (S.view === "action") S.selectedDuty = slug;
  else S.previewDuty = slug;''',
  '''  if (S.view === "action") S.selectedDuty = slug;''',
  "no preview opened after an import before ACTION SELECTION"),
 ('''  if (S.view === "action") S.selectedDuty = slug;
  else S.previewDuty = slug;''',
  '''  S.previewDuty = slug;''',
  "a preview opened in ACTION SELECTION instead of a selection"),
 ('''  if (S.view === "action") S.selectedDuty = slug;
  else S.previewDuty = slug;
  commitPanels();''',
  '''  if (S.view === "action") S.selectedDuty = slug;
  else S.previewDuty = slug;
  S.view = "action";
  commitPanels();''',
  "the import changing which view state is on screen"),

 # ---- the readout --------------------------------------------------------------------------
 ('  var lost = ir > sr ? 1 - sr / ir : 1 - ir / sr;',
  '  var lost = Math.abs(ir - sr);',
  "the cover crop measured as a ratio difference rather than a fraction lost"),
 ('word: lost < 0.05 ? "minimal" : lost < 0.15 ? "slight" : "substantial",',
  'word: lost < 0.001 ? "minimal" : lost < 0.002 ? "slight" : "substantial",',
  "a 2% ratio difference reported as substantial"),
 ('function ratioText(w, h){ return h ? (w / h).toFixed(3) : "--"; }',
  'function ratioText(w, h){ return h ? (w / h).toFixed(1) : "--"; }',
  "the ratio rounded until 2.000 and 2.038 look identical"),
 ('      noteDims(key, probe.naturalWidth, probe.naturalHeight);',
  '      noteDims(key, probe.naturalHeight, probe.naturalWidth);',
  "width and height reported the wrong way round"),

 # ---- the production export ------------------------------------------------------------------
 ('      d[a.key] = {name: act.name, shortLabel: act.shortLabel};',
  '      d[a.key] = {name: act.name, shortLabel: act.shortLabel, scenic: imgSrc(act.scenic)};',
  "image bytes leaking into the production game layout"),
 ('      d[a.key] = {name: act.name, shortLabel: act.shortLabel};',
  '      d[a.key] = {name: act.name, shortLabel: act.shortLabel,\n'
  '                  scenicName: act.scenicName};',
  "an artwork filename added to the production export"),
]

run = MutationRun("V4.3 duty-art mutations vs accept43", total=len(MUTS))
for old, new, label in MUTS:
    try:
        mutated = replace_exactly_once(BASE, old, new, label)
    except MutationTargetError as err:
        run.record_invalid(label, err)
        continue
    TMP.write_text(mutated)
    r = subprocess.run([shutil.which("node"), str(HERE / "accept43.mjs"), TMP.as_uri()],
                       capture_output=True, text=True, cwd=str(ROOT))
    out = (r.stdout + r.stderr).strip().splitlines()
    fails = [x for x in out if x.startswith("FAIL")]
    crashed = not any(re.search(r"\d+/\d+ passed", ln) for ln in out)
    run.record(label, r.returncode != 0, out[-1] if out else "(no output)", fails[:2], False,
               crashed)

TMP.unlink(missing_ok=True)
raise SystemExit(run.report())
