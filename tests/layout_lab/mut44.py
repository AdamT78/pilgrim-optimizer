"""Break each tithe-token behaviour on purpose and see whether accept44 notices.

The suite is the argument for the triangle, so the mutations it has to survive are the ones that
would quietly put the old flex pyramid back: a spread that depends on the size, a size that moves
the centres, a migration that runs in the wrong place and silently resets the arrangement it was
supposed to recover. Every one of those looks fine on screen until you touch a slider.
"""
import pathlib, re, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mutation_tools import MutationRun, MutationTargetError, replace_exactly_once

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "lab.html"
TMP = HERE / "lab_mut44.html"
BASE = SRC.read_text()

# (target, replacement, label) or (target, replacement, label, benign)
MUTS = [
 # ---- the token is the whole picture -------------------------------------------------------
 ('.tok{display:block;object-fit:contain;background:none;border:0;border-radius:0}',
  '.tok{display:block;object-fit:contain;border:1px solid #6b5c3e;border-radius:50%}',
  "a second rim drawn around the token art"),
 ('''  if (haveImage(r.icon)){
    return slot + '<img class=tok''',
  '''  if (haveImage(r.icon)){
    return slot + '<span class=res style="width:100%;height:100%"><img class=tok''',
  "the token put back inside the old brown disc"),

 # ---- the fallback -------------------------------------------------------------------------
 ("  if (haveImage(r.icon)){\n    return slot + '<img class=tok src=\"'", "  if (r.icon){\n    return slot + '<img class=tok src=\"'",
  "a remembered key with no bytes rendering as a broken image"),
 ('''  return slot + '<span class=res title="''',
  '''  return slot + '<span class=res style="display:none" title="''',
  "the letter fallback removed, leaving an empty card with no assets"),

 # ---- THE TRIANGLE -------------------------------------------------------------------------
 # Each of these still draws three tokens in a plausible-looking clump. What they break is the
 # relationship between the two controls, which is the whole design.
 ('  return [{x: 0, y: -h / 2}, {x: -s / 2, y: h / 2}, {x: s / 2, y: h / 2}];',
  '  return [{x: 0, y: -h / 2}, {x: -s / 2, y: h / 2}, {x: s / 2, y: h / 3}];',
  "one vertex off the triangle, so the three sides stop being equal"),
 ('  return [{x: 0, y: -h / 2}, {x: -s / 2, y: h / 2}, {x: s / 2, y: h / 2}];',
  '  return [{x: 0, y: h / 2}, {x: -s / 2, y: -h / 2}, {x: s / 2, y: -h / 2}];',
  "the triangle turned apex down"),
 ('  return [{x: 0, y: -h / 2}, {x: -s / 2, y: h / 2}, {x: s / 2, y: h / 2}];',
  '  return [{x: -s / 8, y: -h / 2}, {x: -s / 2, y: h / 2}, {x: s / 2, y: h / 2}];',
  "the apex no longer centred over the base"),
 ('  var s = tokenSpread(), h = s * Math.sqrt(3) / 2;',
  '  var s = tokenSpread(), h = s;',
  "the triangle stretched vertically, so the side is no longer the spread"),
 ('''function tokenPoints(){
  var s = tokenSpread()''',
  '''function tokenPoints(){
  var s = tokenSpread() + tokenSize()''',
  "the spread quietly depending on the size again, as the old gap did"),

 # ---- the container the vertices are measured in -------------------------------------------
 # This is the one that reintroduces the drift: a container sized to the whole arrangement grows
 # with the tokens, and once it outgrows the card the flex column stops centring it.
 ('''function tokenTriangle(){
  var s = tokenSpread();
  return {width: s, height: s * Math.sqrt(3) / 2};
}''',
  '''function tokenTriangle(){ return tokenBounds(); }''',
  "the container sized to the whole arrangement, so growing a token shifts all three"),
 # THE ORIGIN ALONE. An earlier version of this zeroed `tb` in the render block instead, which
 # sizes the container AND moves the origin from the same value -- the two cancel exactly and
 # nothing moves. It survived, and it was right to: it was a mutation that changed nothing.
 ("""  var slot = '<span class=slot style="left:' + (tb.width / 2 + pt.x) + 'px;top:'
           + (tb.height / 2 + pt.y) + 'px;""",
  """  var slot = '<span class=slot style="left:' + pt.x + 'px;top:'
           + pt.y + 'px;""",
  "the vertices measured from the container's corner rather than its middle"),
 ('  .slot{position:absolute;display:grid;place-items:center;transform:translate(-50%,-50%)}',
  '  .slot{position:absolute;display:grid;place-items:center}',
  "the tokens hung from their corners rather than centred on their vertices"),

 # ---- the shared size ----------------------------------------------------------------------
 ('''function setTokenSize(v, soon){
  S.tithe.tokenSize = clamp(Math.round(v), HELPERS.tokenSize[0], HELPERS.tokenSize[1]);''',
  '''function setTokenSize(v, soon){
  S.tithe.tokenSize = clamp(Math.round(v), HELPERS.tokenSize[0], HELPERS.tokenSize[1]);
  S.tithe.height = S.tithe.height + 10;''',
  "the Tithe box growing to follow the token size"),
 ('function tokenSize(){ return clamp(Math.round(S.tithe.tokenSize), HELPERS.tokenSize[0],',
  'function tokenSize(){ return clamp(Math.round(S.tithe.tokenSize * 1.5), HELPERS.tokenSize[0],',
  "the slots drawn at something other than the stated size"),
 ("""       + 'px;height:' + box + 'px;font-size:'""",
  """       + 'px;height:' + (box - 6) + 'px;font-size:'""",
  "a placeholder that is not square, so the disc is an ellipse"),

 # ---- the spread ---------------------------------------------------------------------------
 ('''function setTokenSpread(v, soon){
  S.tithe.tokenSpread = clamp(Math.round(v), HELPERS.tokenSpread[0], HELPERS.tokenSpread[1]);
  commit(soon);
}''',
  '''function setTokenSpread(v, soon){
  commit(soon);
}''',
  "the spread control writing nothing"),
 ('function tokenSpread(){ return clamp(Math.round(S.tithe.tokenSpread), HELPERS.tokenSpread[0],',
  'function tokenSpread(){ return clamp(Math.round(S.tithe.tokenSpread) + 8, HELPERS.tokenSpread[0],',
  "the drawn side not the number the control reports"),
 # HELPERS is inlined by the generator as one long JSON line, so the marker is the neighbouring
 # key rather than the generator's own indented source.
 ('"tokenSize": [28, 160], "tokenSpread": [0, 200]',
  '"tokenSize": [28, 160], "tokenSpread": [20, 200]',
  "a floor under the spread, so three tokens can no longer be stacked on one point"),

 # ---- old sessions -------------------------------------------------------------------------
 # THE MIGRATION RUNS IN migrate(), ON THE INCOMING FILE. Moved after deepMerge it does nothing
 # at all, because the defaults have filled the hole it looks for -- and the file's arrangement
 # is replaced by the default one with no sign that anything went wrong. That was a real bug in
 # this build, caught by TEST 30 and by nothing else.
 ('''    if (d.tithe.tokenSpread === undefined && d.tithe.tokenGap !== undefined''',
  '''    if (false && d.tithe.tokenGap !== undefined''',
  "a pre-triangle session silently reset to the default spread"),
 ('      d.tithe.tokenSpread = tsz + Math.round(+d.tithe.tokenGap);',
  '      d.tithe.tokenSpread = Math.round(+d.tithe.tokenGap);',
  "the gap read as if it were already a centre-to-centre distance"),
 # This survived the first run, because applyState deleted `scale` a second time and the two
 # covered for each other: break either and nothing failed, so neither could be shown to be
 # doing the work. The second delete is gone and this is now the only one.
 ('''    if (Array.isArray(d.tithe.resources)){
      d.tithe.resources.forEach(function(r){ if (r) delete r.scale; });
    }''', '',
  "the dropped per-resource scale left in the state"),
 ('''  S.tithe.resources.forEach(function(r){
    if (r.icon === undefined) r.icon = null;''',
  '''  S.tithe.resources.forEach(function(r){
    if (false) r.icon = null;''',
  "an old session left without icon fields"),
 ('''  S.tithe.tokenSize = clamp(Math.round(+S.tithe.tokenSize || DEFAULT_STATE.tithe.tokenSize),
                            HELPERS.tokenSize[0], HELPERS.tokenSize[1]);''',
  '''  S.tithe.tokenSize = +S.tithe.tokenSize || DEFAULT_STATE.tithe.tokenSize;''',
  "an imported token size trusted without clamping"),
 ('''  S.tithe.tokenSpread = clamp(Math.round(
      S.tithe.tokenSpread === undefined || S.tithe.tokenSpread === null
        || isNaN(+S.tithe.tokenSpread)
          ? DEFAULT_STATE.tithe.tokenSpread : +S.tithe.tokenSpread),
      HELPERS.tokenSpread[0], HELPERS.tokenSpread[1]);''',
  '''  S.tithe.tokenSpread = clamp(Math.round(+S.tithe.tokenSpread
      || DEFAULT_STATE.tithe.tokenSpread), HELPERS.tokenSpread[0], HELPERS.tokenSpread[1]);''',
  "a deliberate spread of 0 silently turned into the default"),

 # ---- the session ---------------------------------------------------------------------------
 ('    (S.tithe.resources || []).forEach(function(r){ mark(r.icon); });', '',
  "a session exported with images losing the token art"),

 # ---- the caption ----------------------------------------------------------------------------
 ('''#titheObj .tl{position:absolute;left:0;right:0;bottom:10px;text-align:center;
  font:600 17px/1.2 Georgia,serif;letter-spacing:.11em;text-transform:uppercase;''',
  '''#titheObj .tl{position:absolute;left:0;right:0;bottom:10px;text-align:center;
  font:600 14px/1.1 Georgia,serif;letter-spacing:.15em;text-transform:uppercase;''',
  "the Tithe caption drifting away from the action-artwork caption"),
 ("#titheObj .tl{position:absolute;left:0;right:0;bottom:10px;text-align:center;",
  "#titheObj .tl{position:absolute;left:0;right:0;bottom:10px;text-align:left;",
  "the caption left-aligned rather than centred"),
 ("#titheObj .tl{position:absolute;left:0;right:0;bottom:10px;text-align:center;",
  "#titheObj .tl{position:absolute;left:0;right:0;top:6px;text-align:center;",
  "the caption moved back above the tokens"),
 # BENIGN AND SAID SO. The caption is absolutely positioned, so where it sits in the markup has
 # no effect on where it is drawn; moving it is not a change the page can show. Keeping it as a
 # declared no-op is the honest version of the entry it replaced, which was written as an
 # ordinary mutation, survived, and was read for a while as a hole in the caption tests.
 ('''                  '<span class=nm>tithe</span>' + pyr + '<div class=tl>' + esc(T.label)
                    + '</div>',''',
  '''                  '<span class=nm>tithe</span><div class=tl>' + esc(T.label) + '</div>'
                    + pyr,''',
  "the caption earlier in the markup, which an absolute position makes invisible", True),

 # ---- a drag must survive itself -------------------------------------------------------------
 ('''function setTokenSize(v, soon){
  S.tithe.tokenSize = clamp(Math.round(v), HELPERS.tokenSize[0], HELPERS.tokenSize[1]);
  commit(soon);
}''',
  '''function setTokenSize(v, soon){
  S.tithe.tokenSize = clamp(Math.round(v), HELPERS.tokenSize[0], HELPERS.tokenSize[1]);
  commit(soon); panels();
}''',
  "the size control rebuilding the panel it is being dragged in"),
 ('''  S.tithe.tokenSpread = clamp(Math.round(v), HELPERS.tokenSpread[0], HELPERS.tokenSpread[1]);
  commit(soon);
}''',
  '''  S.tithe.tokenSpread = clamp(Math.round(v), HELPERS.tokenSpread[0], HELPERS.tokenSpread[1]);
  commit(soon); panels();
}''',
  "the spread control rebuilding the panel it is being dragged in"),
 ('''  syncHelperInputs();
  syncTokenInputs();''', '''  syncHelperInputs();''',
  "the tithe controls never re-synced from render"),
 ('''function syncTokenInputs(){
  if (!el("tkSizeN")) return;''',
  '''function syncTokenInputs(){
  if (!el("tkSizeN")) return;
  panels();''',
  "the sync rebuilding the panel instead of writing into it"),
 ('    if (!e || e === document.activeElement) return;\n    if (String(e.value) !== String(v)) e.value = v;\n  }\n  set(el("tkSizeN")',
  '    if (!e) return;\n    if (String(e.value) !== String(v)) e.value = v;\n  }\n  set(el("tkSizeN")',
  "the tithe sync stamping on the control the caret is in"),
 ('  if (read) read.innerHTML = tokenReadout();', '',
  "the derived readout frozen at whatever it said when the panel was built"),

 # ---- the image pool: a key must never be handed out twice -----------------------------------
 ('''  S = deepMerge(clone(DEFAULT_STATE), d);
  // Before anything can hand out a new key, take every one this state already uses out of
  // circulation -- see reserveImageKeys.
  reserveImageKeys(S);''',
  '''  S = deepMerge(clone(DEFAULT_STATE), d);''',
  "the pool counter left behind the keys the state already claims"),
 ('  if (max > IMG_SEQ) IMG_SEQ = max;', '  if (max > IMG_SEQ) IMG_SEQ = max - 1;',
  "the reservation off by one, so the last remembered key is handed out again"),
 ('''  JSON.stringify(d).replace(/"im(\\d+)"/g, function(m, n){
    n = +n; if (n > max) max = n; return m;
  });''',
  '''  JSON.stringify(d).replace(/"im(\\d+)"/g, function(m, n){
    n = +n; if (n < max) max = n; return m;
  });''',
  "the reservation taking the lowest key rather than the highest"),

 # ---- the production export -------------------------------------------------------------------
 ('''            tokenSize: tokenSize(), tokenSpread: tokenSpread(),
''', '',
  "the token sizing missing from the production export"),
 ('''              return {key: r.key, name: r.name, iconName: r.iconName || null}; })},''',
  '''              return {key: r.key, name: r.name, icon: r.icon,
                      iconName: r.iconName || null}; })},''',
  "an image-pool key leaking into the production export"),
 ('            tokenSize: tokenSize(), tokenSpread: tokenSpread(),',
  '            tokenSize: tokenSize(), tokenGap: tokenSize(), tokenSpread: tokenSpread(),',
  "the field the flex build used left in the export beside its replacement"),
]

run = MutationRun("V4.4 tithe-token mutations vs accept44", total=len(MUTS))
for entry in MUTS:
    old, new, label = entry[0], entry[1], entry[2]
    benign = len(entry) > 3 and entry[3]
    try:
        mutated = replace_exactly_once(BASE, old, new, label)
    except MutationTargetError as err:
        run.record_invalid(label, err); continue
    TMP.write_text(mutated)
    r = subprocess.run([shutil.which("node"), str(HERE / "accept44.mjs"), TMP.as_uri()],
                       capture_output=True, text=True, cwd=str(HERE))
    out = (r.stdout + r.stderr).strip().splitlines()
    fails = [x for x in out if x.startswith("FAIL")]
    crashed = not any(re.search(r"\d+/\d+ passed", ln) for ln in out)
    run.record(label, r.returncode != 0, out[-1] if out else "(no output)", fails[:2], benign,
               crashed)

TMP.unlink(missing_ok=True)
raise SystemExit(run.report())
