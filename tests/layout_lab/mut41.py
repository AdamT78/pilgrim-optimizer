"""Put each of the four bugs back and confirm the numbered acceptance test catches it.

A suite that passed first time has not been shown to work -- it has been shown not to have failed.
These are the exact behaviours the brief describes as wrong, reintroduced one at a time.
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
TMP = OUT / "lab_mut41.html"
BASE = SRC.read_text()

# A default state claiming an asset ratio it has not got is invisible in the browser -- the
# warning is gated on an asset actually being loaded -- so that one is guarded in the pytest
# suite instead, where the default state is read directly. See mut4py.py.
MUTS = [
 # ---- 1. the asset reshapes the layout again ------------------------------------------------
 ('o.assetRatio = vb > 0 ? vb : (ratio > 0 ? ratio : null);',
  'o.assetRatio = vb > 0 ? vb : (ratio > 0 ? ratio : null);\n'
  '    if (o.assetRatio){ o.naturalRatio = o.assetRatio;\n'
  '                       o.height = Math.round(o.width * o.naturalRatio); syncAttached(); }',
  "a loaded asset reshaping the wheel"),
 ('    } else if (ratioMatches(o.assetRatio)){',
  '    } else if (true){',
  "a mismatched asset reported as matching"),
 ('#wheelObj img{width:100%;height:100%;display:block;object-fit:contain}',
  '#wheelObj img{width:100%;height:100%;display:block;object-fit:fill}',
  "a mismatched asset stretched to fill the box"),
 ('''    S.wheel.image = keepImg; S.wheel.imageName = keepName;
    S.wheel.assetRatio = keepAR === undefined ? null : keepAR;''',
  '''    S.wheel.image = null; S.wheel.imageName = null;
    S.wheel.assetRatio = keepAR === undefined ? null : keepAR;''',
  "reset throwing the loaded artwork away"),
 ('''  S.wheel.naturalRatio = WHEEL_RATIO;
  S.wheel.ratioSource = "builtin";
  S.wheel.height = Math.round(S.wheel.width * WHEEL_RATIO);''',
  '''  if (!(S.wheel.naturalRatio > 0)) S.wheel.naturalRatio = WHEEL_RATIO;''',
  "an imported ratio left unnormalised"),
 # ---- 2. the preview dismissed by anything that is not a card ---------------------------------
 ('''    } else if (!node){
      if (S.previewDuty){ S.previewDuty = null; render(); panels(); save(true); }''',
  '''    } else if (!node || node.dataset.kind !== "card"){
      if (S.previewDuty){ S.previewDuty = null; render(); panels(); save(true); }''',
  "the old dismiss-on-anything rule"),
 # TWO GUARDS, EITHER SUFFICIENT: the handler declines to call togglePreview in ACTION, and
 # togglePreview declines to act if it is called. Removing one is a no-op, which is the point of
 # having two -- so the mutation that means anything removes both.
 ('''    if (node && node.dataset.kind === "card" && S.view !== "action"){
      togglePreview(node.dataset.id);''',
  '''    if (node && node.dataset.kind === "card"){
      togglePreview(node.dataset.id);''',
  "one of the two ACTION guards removed (expected to be harmless)", True),
 ('''function togglePreview(slug){
  if (S.view === "action") return;''',
  '''function togglePreview(slug){''',
  "the other one removed (also expected harmless)", True),
 ('''    if (node && node.dataset.kind === "card" && S.view !== "action"){
      togglePreview(node.dataset.id);''',
  '''    if (node && node.dataset.kind === "card"){
      if (S.view === "action"){ S.previewDuty = node.dataset.id; render(); panels(); }
      else togglePreview(node.dataset.id);''',
  "cards previewing during ACTION SELECTION"),
 # ---- 3. the export dropping what the UI needs --------------------------------------------------
 ('''             size: S.status.size, align: S.status.align, opacity: S.status.opacity,
             visible: !!S.status.visible, byView: msgs},''',
  '''             },''',
  "the instruction exported as a bare box"),
 ('''    highlight: {width: H.width, height: H.height, dy: H.dy, style: H.style,
                visible: !!H.visible, opacity: H.opacity, colour: H.colour},''',
  '''''',
  "the reached-duty highlight left out"),
 ('''                         fit: e.fit, opacity: e.opacity, visible: !!e.visible,
                         labelVisible: !!e.labelVisible, labelSize: e.labelSize};''',
  '''                         };''',
  "the artwork slots exported without their presentation"),
 ('''            resources: (S.tithe.resources || []).map(function(r){
              return {key: r.key, name: r.name}; })},''',
  '''            },''',
  "Tithe exported without its resources"),
 ('''            ratio: WHEEL_RATIO, ground: !!S.wheel.ground, opacity: S.wheel.opacity},''',
  '''            },''',
  "the wheel exported without its ratio"),
 ('''    var d = {name: D.name,
             card: {x: cd.x, y: cd.y, width: cd.width, height: cd.height,
                    visible: !!cd.visible}};''',
  '''    var d = {name: D.name,
             card: {x: cd.x, y: cd.y, width: cd.width, height: cd.height,
                    visible: !!cd.visible, locked: !!cd.locked}};''',
  "lock state leaking into the export"),
 ('''    d.figures = {x: F.x, y: F.y, u: F.u, v: F.v,
                 spacing: F.spacing, arrangement: F.arrangement, attached: !!F.attached};''',
  '''    d.figures = {x: F.x, y: F.y, u: F.u, v: F.v, count: F.count, seats: F.seats,
                 spacing: F.spacing, arrangement: F.arrangement, attached: !!F.attached};''',
  "this session's occupancy exported as layout"),
 # ---- 4. the misleading hover -----------------------------------------------------------------------
 ('body.clean .card.previewable:hover{filter:brightness(1.12);cursor:pointer}',
  'body.clean .card:hover{filter:brightness(1.12);cursor:pointer}',
  "the hover affordance back on every card"),
 ('    if (S.view !== "action") cls += " previewable";',
  '    cls += " previewable";',
  "every card marked previewable regardless of state"),
]

run = MutationRun("V4.1 page mutations vs accept41", total=len(MUTS))
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
    r = subprocess.run([shutil.which("node"), str(HERE / "accept41.mjs"), TMP.as_uri()],
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
