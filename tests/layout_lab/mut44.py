"""Break each tithe-token behaviour on purpose and see whether accept44 notices."""
import os, pathlib, re, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mutation_tools import MutationRun, MutationTargetError, replace_exactly_once

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = pathlib.Path(os.environ.get("LAYOUT_LAB_OUT", ROOT / "out"))
SRC = OUT / "lab.html"
TMP = OUT / "lab_mut44.html"
BASE = SRC.read_text()

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
 ('    if (haveImage(r.icon)){', '    if (r.icon){',
  "a remembered key with no bytes rendering as a broken image"),
 ('''  return slot + '<span class=res title="''',
  '''  return slot + '<span class=res style="display:none" title="''',
  "the letter fallback removed, leaving an empty card with no assets"),

 # ---- the fixed slot: scale must not move neighbours ---------------------------------------
 ('''  var slot = '<span class=slot style="width:' + box + 'px;height:' + box + 'px">';''',
  '''  var slot = '<span class=slot style="width:' + px + 'px;height:' + px + 'px">';''',
  "the slot following the per-token scale, so one token shoves the others"),
 ('function tokenPx(r){ return Math.round(tokenSize() * tokenScale(r) / 100); }',
  'function tokenPx(r){ return tokenSize(); }',
  "per-resource scale ignored entirely"),
 ('function tokenPx(r){ return Math.round(tokenSize() * tokenScale(r) / 100); }',
  'function tokenPx(r){ return Math.round(tokenSize() + tokenScale(r) - 100); }',
  "scale applied as an offset rather than a percentage"),

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

 # ---- the gap ------------------------------------------------------------------------------
 ('''    var pyr = '<div class=pyr style="gap:' + tokenGap() + 'px"><div class=pr style="gap:'
            + tokenGap() + 'px">''',
  '''    var pyr = '<div class=pyr style="gap:7px"><div class=pr style="gap:'
            + tokenGap() + 'px">''',
  "the vertical gap frozen, so one control no longer drives both axes"),

 # ---- old sessions -------------------------------------------------------------------------
 ('''    r.scale = clamp(Math.round(+r.scale || 100), HELPERS.tokenScale[0], HELPERS.tokenScale[1]);''',
  '''    if (r.scale === undefined) r.scale = 100;''',
  "an imported scale trusted without clamping"),
 ('''  S.tithe.resources.forEach(function(r){
    if (r.icon === undefined) r.icon = null;''',
  '''  S.tithe.resources.forEach(function(r){
    if (false) r.icon = null;''',
  "an old session left without icon fields"),
 ('''  S.tithe.tokenSize = clamp(Math.round(+S.tithe.tokenSize || DEFAULT_STATE.tithe.tokenSize),
                            HELPERS.tokenSize[0], HELPERS.tokenSize[1]);''',
  '''  S.tithe.tokenSize = +S.tithe.tokenSize || DEFAULT_STATE.tithe.tokenSize;''',
  "an imported token size trusted without clamping"),
 ('''  S.tithe.tokenGap = clamp(Math.round(
      S.tithe.tokenGap === undefined || S.tithe.tokenGap === null || isNaN(+S.tithe.tokenGap)
        ? DEFAULT_STATE.tithe.tokenGap : +S.tithe.tokenGap),
      HELPERS.tokenGap[0], HELPERS.tokenGap[1]);''',
  '''  S.tithe.tokenGap = clamp(Math.round(+S.tithe.tokenGap || DEFAULT_STATE.tithe.tokenGap),
      HELPERS.tokenGap[0], HELPERS.tokenGap[1]);''',
  "a deliberate gap of 0 silently turned into the default"),

 # ---- the session ---------------------------------------------------------------------------
 ('    (S.tithe.resources || []).forEach(function(r){ mark(r.icon); });', '',
  "a session exported with images losing the token art"),

 # ---- the production export -------------------------------------------------------------------
 ('''            tokenSize: tokenSize(), tokenGap: tokenGap(),
''', '',
  "the token sizing missing from the production export"),
 ('''              return {key: r.key, name: r.name, iconName: r.iconName || null,
                      scale: tokenScale(r)}; })},''',
  '''              return {key: r.key, name: r.name, icon: r.icon,
                      iconName: r.iconName || null, scale: tokenScale(r)}; })},''',
  "an image-pool key leaking into the production export"),
]

run = MutationRun("V4.4 tithe-token mutations vs accept44", total=len(MUTS))
for old, new, label in MUTS:
    try:
        mutated = replace_exactly_once(BASE, old, new, label)
    except MutationTargetError as err:
        run.record_invalid(label, err); continue
    TMP.write_text(mutated)
    r = subprocess.run([shutil.which("node"), str(HERE / "accept44.mjs"), TMP.as_uri()],
                       capture_output=True, text=True, cwd=str(ROOT))
    out = (r.stdout + r.stderr).strip().splitlines()
    fails = [x for x in out if x.startswith("FAIL")]
    crashed = not any(re.search(r"\d+/\d+ passed", ln) for ln in out)
    run.record(label, r.returncode != 0, out[-1] if out else "(no output)", fails[:2], False, crashed)

TMP.unlink(missing_ok=True)
raise SystemExit(run.report())
