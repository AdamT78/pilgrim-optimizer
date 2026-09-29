"""Break the V4 generator and template on purpose and see whether the pytest suite notices.

Every mutation is a change the V4 brief forbids. A MISSED line means the guard is decorative.
The __pycache__ dirs are cleared per run: a mutation that is the same byte length as the text it
replaces leaves size and mtime unchanged, so CPython reuses the cached bytecode and a real
failure reads as a pass. That has happened twice on this file.
"""
import pathlib
import shutil
import subprocess
import atexit
import signal
import sys

from mutation_tools import (MutationRun, MutationTargetError, replace_exactly_once,
                            replace_regex_exactly_once)

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LAB = ROOT / "ui" / "board_v2" / "layout_lab"
TESTS = HERE          # the layout lab guards live beside this file
T = LAB / "duty_wheel_layout_lab.html.tmpl"
G = LAB / "generate_layout_lab.py"
TB, GB = T.read_text(), G.read_text()

PALETTE_FACE = '"#efe3c8": "#3a3d45",'
PALETTE_HUB = '"#e8dcc0": "#23262b",'
RAISE_ON_MISS = (
    "        if not n:\n"
    "            raise SystemExit(\"the built-in wheel has no %s in it, so the lab's palette no longer \"\n"
    "                             \"describes the drawing it is colouring\" % old)")
_STRIPPED = 're.sub(r"^\\s*<\\?xml[^>]*\\?>\\s*", "", text).strip()'

MUTS = [
 # ---- V4.2: the layout helpers ------------------------------------------------------------------
 ("gen", '"wheelW": [600, CANVAS_W],', '"wheelW": [600, 2000],',
  "studio_only", "a wheel range that lets the slider leave the module"),
 ("gen", '"rowRight": CANVAS_W - (BAND["x"] + BAND["width"]),', '"rowRight": 60,',
  "studio_only", "the fit margin picked separately from the band's own"),
 ("gen", '"cardH": [80, 300],', '"cardH": [80, 120],',
  "studio_only", "a card range the starting layout is already outside"),
 ("tmpl", "  DUTY_ORDER.forEach(function(s){ S.duties[s].card.height = v; });\n  commit(soon);",
          "  DUTY_ORDER.forEach(function(s){ S.duties[s].card.height = v; });\n"
          "  S.tithe.y = 999;\n  commit(soon);",
  "no_helper_pushes", "the card height control shoving another band"),
 ("tmpl", "  L.height = v; R.height = v;\n  R.y = L.y;",
          "  L.height = v; R.height = v;\n  R.y = L.y;\n  S.city.height = v;",
  "no_helper_pushes", "the linked artwork height dragging the City with it"),
 ("tmpl", "  R.x = Math.round(L.x + L.width + gap);",
          "  L.x = L.x + 1;\n  R.x = Math.round(L.x + L.width + gap);",
  "no_helper_pushes", "the row's left anchor walking sideways"),
 ("tmpl", "  S.wheel.x = Math.round((CANVAS_W - S.wheel.width) / 2);\n  syncAttached();",
          "  S.wheel.x = Math.round((CANVAS_W - S.wheel.width) / 2);\n  S.wheel.y = 438;\n  syncAttached();",
  "no_helper_pushes", "centre wheel x also writing y"),
 ("tmpl", "function rowGapCommon(){", "function rowGapCommonX(){",
  "read_the_geometry", "a derived reading removed"),
 ("gen", '"ratioSource": "builtin",', '"ratioSource": "builtin", "rowGap": 12,',
  "read_the_geometry", "a remembered gap put into the state"),

 # ---- V4.1: the four corrections ---------------------------------------------------------------
 # ANCHORED TO THE DECLARATION, NOT TO THE VALUE. Whatever the current version is, this finds
 # it and breaks it; there is no version string here to go stale.
 ("gen", 're:BUILD_VERSION = "[0-9][0-9.]*"', 'BUILD_VERSION = "4.0"',
  "build_label_moved", "the build label left at an older version"),
 ("gen", "STATE_VERSION = 4", "STATE_VERSION = 5",
  "build_label_moved", "the schema bumped for a corrective release"),
 ("gen", '"assetRatio": None, "assetRatioSource": None,',
         '"assetRatio": 0.5624, "assetRatioSource": "viewBox",',
  "art_in_the_box", "the default state claiming an asset ratio it has not got"),
 ("gen", "    if abs(ratio - DESIGN_RATIO) > RATIO_TOLERANCE:", "    if False:",
  "art_in_the_box", "the 32 degree invariant no longer refusing anything"),
 ("gen", "DESIGN_RATIO = 0.5299", "DESIGN_RATIO = 0.5624",
  "art_in_the_box", "the design ratio moved to the 1.778 wheel's"),
 ("gen", "RATIO_TOLERANCE = 0.0005", "RATIO_TOLERANCE = 0.5",
  "art_in_the_box", "the tolerance widened until it accepts anything"),
 ("tmpl", "#wheelObj img{width:100%;height:100%;display:block;object-fit:contain}",
          "#wheelObj img{width:100%;height:100%;display:block;object-fit:fill}",
  "art_in_the_box", "a mismatched asset stretched rather than contained"),
 ("tmpl", "  S.wheel.naturalRatio = WHEEL_RATIO;\n  S.wheel.ratioSource = \"builtin\";",
          "  if (!(S.wheel.naturalRatio > 0)) S.wheel.naturalRatio = WHEEL_RATIO;",
  "art_in_the_box", "the import normalisation made conditional again"),
 ("tmpl", "    o.assetRatio = vb > 0 ? vb : (ratio > 0 ? ratio : null);",
          "    o.assetRatio = vb > 0 ? vb : (ratio > 0 ? ratio : null);\n    o.naturalRatio = o.assetRatio || o.naturalRatio;",
  "art_in_the_box", "a loaded asset writing the layout ratio again"),
 ("tmpl", "    } else if (!node){", "    } else if (!node || node.dataset.kind !== \"card\"){",
  "empty_stage_click", "the preview dismissed by anything that is not a card"),
 ("tmpl", "body.clean .card.previewable:hover{filter:brightness(1.12);cursor:pointer}",
          "body.clean .card:hover{filter:brightness(1.12);cursor:pointer}",
  "advertise_a_click", "the hover affordance back on every card"),
 ("tmpl", '    if (S.view !== "action") cls += " previewable";', '    cls += " previewable";',
  "advertise_a_click", "every card marked previewable regardless of state"),

 # ---- the module and the wheel -----------------------------------------------------------------
 ("gen", "WHEEL_W = min(_fits_width, _fits_height) // 2 * 2", "WHEEL_W = 950",
  "takes_whatever_fits", "the wheel shrunk back to a V3 width"),
 ("gen", "WHEEL_W = min(_fits_width, _fits_height) // 2 * 2",
         "WHEEL_W = _fits_height // 2 * 2",
  "takes_whatever_fits", "only the height ceiling checked, so the wheel leaves the module"),
 ("gen", "WHEEL_MARGIN_MIN = 14", "WHEEL_MARGIN_MIN = 90",
  "takes_whatever_fits", "the margins widened until the wheel stops dominating"),
 ("gen", "WHEEL_H = round(WHEEL_W * WHEEL_RATIO)", "WHEEL_H = round(WHEEL_W * 0.44)",
  "shape_is_the_assets or takes_whatever_fits", "the box no longer carrying the asset's ratio"),
 ("gen", '"naturalRatio": WHEEL_RATIO,', '"naturalRatio": WHEEL_H / WHEEL_W,',
  "shape_is_the_assets", "the rounded box ratio stored instead of the asset's"),
 ("gen", '"ratioSource": "builtin",', '"ratioSource": "elevation",',
  "shape_is_the_assets", "the ratio claiming to come from an elevation"),
 ("gen", "WHEEL_RATIO = WHEEL_VIEW_H / WHEEL_VIEW_W", "WHEEL_RATIO = math.sin(math.radians(32.0))",
  "shape_is_the_assets", "sin(32) back as the source of the shape"),
 # ---- the recolour ------------------------------------------------------------------------------
 ("gen", PALETTE_FACE, PALETTE_FACE.replace('"#3a3d45"', '"#efe3c8"'),
  "recoloured_into", "the faces left in the builder's parchment"),
 ("gen", PALETTE_HUB, PALETTE_HUB.replace('"#23262b"', '"#3a3d45"'),
  "recoloured_into", "the hub given the same grey as the faces"),
 ("gen", RAISE_ON_MISS, "        pass",
  "recoloured_into", "a palette that no longer matches failing silently"),
 ("gen", "pattern = re.compile(re.escape(old), re.IGNORECASE)",
         "pattern = re.compile(re.escape(old))",
  "recoloured_into", "the colour match made case-sensitive"),
 ("gen", "    return recolour(" + _STRIPPED + ")", "    return " + _STRIPPED + "",
  "recoloured_into", "the recolour skipped altogether"),
 ("gen", 'm = re.search(r\'\\bviewBox\\s*=\\s*"\\s*([-\\d.eE]+)\\s+([-\\d.eE]+)\\s+([-\\d.eE]+)\\s+([-\\d.eE]+)\\s*"\',',
         'm = re.search(r\'\\bwidth\\s*=\\s*"([-\\d.eE]+)"\\s+height\\s*=\\s*"([-\\d.eE]+)"()()\',',
  "viewbox_is_the_authority", "width/height read instead of the viewBox"),
 ("gen", "return recolour(" + _STRIPPED + ")", "return recolour(text.strip())",
  "viewbox_is_the_authority", "the XML declaration left in the inlined markup"),
 ("gen", "WHEEL_Y = 438\n", "WHEEL_Y = 560\n",
  "top_line or nothing_on_the_wheel or acolyte or takes_whatever_fits",
  "the wheel pushed down, leaving a gap under it"),
 ("gen", 'WHEEL_ASSET = HERE / "assets" / "duty_wheel_v2.svg"',
         'WHEEL_ASSET = HERE.parents[2] / "tools" / "ui_debug" / "generated" / "duty_wheel_v2.svg"',
  "vendored_rather_than_imported", "the asset read from the other tool's output directory"),
 # ---- nothing identifies a duty space ------------------------------------------------------------
 ("gen", '        d["card"] = dict(slots[slug], visible=True, locked=False)',
         '        d["label"] = {"x": 10, "y": 20, "width": 110, "visible": False}\n'
         '        d["card"] = dict(slots[slug], visible=True, locked=False)',
  "nothing_on_the_wheel", "a duty label object put back"),
 ("tmpl", "'<span class=nm>wheel</span>' + wheelInner, WHEEL_Z);",
          "'<span class=nm>wheel</span>' + wheelInner + esc(S.duties.clerical.name), WHEEL_Z);",
  "nothing_on_the_wheel", "a duty named inside the wheel element"),
 # ---- the ribbon ------------------------------------------------------------------------------------
 ("gen", "CARD_X0 = RIBBON[\"x\"] + (RIBBON[\"width\"] - (len(DUTIES) * CARD_W",
         "CARD_X0 = 900 + 0 * (RIBBON[\"width\"] - (len(DUTIES) * CARD_W",
  "eight_reference_cards", "the ribbon pushed off the right edge"),
 ("gen", '''    return {slug: {"x": CARD_X0 + i * (CARD_W + CARD_GAP), "y": RIBBON["y"],''',
         '''    return {slug: {"x": CARD_X0 + (7 - i) * (CARD_W + CARD_GAP), "y": RIBBON["y"],''',
  "eight_reference_cards", "the cards laid out against the wheel's order"),
 # ---- the action band ----------------------------------------------------------------------------------
 ("gen", 'TITHE = {"x": ART_RIGHT["x"] + ART_W + 10,', 'TITHE = {"x": ART_RIGHT["x"] + 40,',
  "action_band", "Tithe overlapping the right-hand artwork"),
 ("gen", 'ART_W, ART_GAP = 375, 15', 'ART_W, ART_GAP = 180, 15',
  "artwork_slots or action_band", "the artworks shrunk below Tithe and the City"),
 ("gen", 'BAND = {"x": 28, "y": 240, "width": 1344, "height": 184}',
         'BAND = {"x": 28, "y": 300, "width": 1344, "height": 184}',
  "action_band or top_line", "the band pushed down onto the wheel"),
 # ---- the wheel's centre ---------------------------------------------------------------------------------
 ("gen", 'TITHE = {"x": ART_RIGHT["x"] + ART_W + 10, "y": BAND["y"], "width": 178,',
         'TITHE = {"x": round(WHEEL_CX - 89), "y": round(WHEEL_CY - 92), "width": 178,',
  "centre_is_left_empty or action_band", "Tithe back in the wheel's centre"),
 ("gen", '"inHand": {"count": 4, "seat": "p1", "label": "ACOLYTES IN HAND"}',
         '"inHand": {"count": 4, "seat": "p1", "label": "ACOLYTES IN HAND",\n'
         '                   "x": 600, "y": 700, "width": 178, "height": 184}',
  "centre_is_left_empty or crowded", "the in-hand pool given a box of its own again"),
 # ---- assets vs geometry ------------------------------------------------------------------------------------
 ("gen", '            d[slot] = {"name": text, "shortLabel": text,',
         '            d[slot] = {"x": 1, "y": 2, "width": 3, "height": 4,\n'
         '                       "name": text, "shortLabel": text,',
  "action_owns_its_assets or game_layout", "geometry back on an action"),
 # ---- the acolyte ring ---------------------------------------------------------------------------------------
 ("gen", "FIG_RX, FIG_RY = round(WHEEL_W * 0.385), round(WHEEL_H * 0.34)",
         "FIG_RX, FIG_RY = round(WHEEL_W * 0.385), round(WHEEL_H * 0.42)",
  "acolyte_at_the_top", "the ring widened until the top figures overhang the band"),
 ("gen", 'ACOLYTE_RATIOS = {"duty": 100, "city": 85, "inHand": 95}',
         'ACOLYTE_RATIOS = {"duty": 160, "city": 85, "inHand": 95}',
  "acolyte_at_the_top", "the acolytes grown until they reach into the band"),
 ("tmpl", "function attachable(kind){ return kind === \"figs\"; }",
          "function attachable(kind){ return kind === \"figs\" || kind === \"art\"; }",
  "each_view_state", "the artwork made wheel-relative"),
 # ---- the highlight ------------------------------------------------------------------------------------------
 ("tmpl", ".hl{position:absolute;pointer-events:none;z-index:22}",
          ".hl{position:absolute;pointer-events:none;z-index:19}",
  "highlight", "the highlight back underneath the wheel"),
 ("tmpl", ".hl{position:absolute;pointer-events:none;z-index:22}",
          ".hl{position:absolute;pointer-events:none;z-index:99}",
  "highlight", "the highlight over the acolytes it points at"),
 ("tmpl", '  if (S.view === "action" && H.visible){', "  if (H.visible){",
  "highlight", "a duty highlighted before anything reached it"),
 # ---- the three states -------------------------------------------------------------------------------------------
 ("tmpl", 'function setView(v){\n  if (!VIEW_STATES.some(function(x){ return x.key === v; })) return;\n  S.view = v;',
          'function setView(v){\n  if (!VIEW_STATES.some(function(x){ return x.key === v; })) return;\n  S.view = v;\n  S.wheel.y = v === "action" ? 430 : 438;',
  "identical_in_all_three", "the wheel nudged between states"),
 ("tmpl", 'if (kind === "art")   return shownDuty() ? ["ready", "sow", "action"] : [];',
          'if (kind === "art")   return ["ready", "sow", "action"];',
  "each_view_state", "artwork on screen before anybody asked for a duty"),
 ("tmpl", 'if (kind === "tithe") return ["action"];',
          'if (kind === "tithe") return ["ready", "sow", "action"];',
  "each_view_state", "Tithe offered while still sowing"),
 ("tmpl", 'function shownDuty(){\n  if (S.view === "action") return reachedDuty();',
          'function shownDuty(){\n  if (S.view === "action") return S.previewDuty || reachedDuty();',
  "each_view_state or two_slots", "a stale preview overriding the reached duty"),
 ("tmpl", 'return (S.previewDuty && S.duties[S.previewDuty]) ? S.previewDuty : null;',
          'return S.previewDuty || null;',
  "each_view_state", "a preview pointed at a duty that does not exist"),
 # ---- the preview is not a choice -----------------------------------------------------------------------------------
 ("tmpl", 'var cls = "art " + e.fit + (isPreview ? "" : " choice");',
          'var cls = "art " + e.fit + " choice";',
  "clean_preview", "a preview dressed as a choice"),
 ("tmpl", 'pv.className = "pv"; pv.textContent = "PREVIEW";',
          'pv.className = "pv"; pv.textContent = "";',
  "clean_preview", "the PREVIEW badge emptied"),
 # ---- the status band ---------------------------------------------------------------------------------------------------
 ("gen", '''    ("sow",    "SOWING",            "Choose the next Duty — {n} Acolytes remaining"),''',
         '''    ("sow",    "SOWING",            "Choose the next Duty — 4 Acolytes remaining"),''',
  "status_band_has_one_message or keeps_its_own", "the sow count typed instead of substituted"),
 ("gen", 'byView={k: {"main": m} for k, _l, m in VIEW_STATES},',
         'byView={k: {"main": m, "context": l} for k, l, m in VIEW_STATES},',
  "status_band_has_one_message or keeps_its_own", "the V3 context strap put back"),
 ("tmpl", "  VIEW_STATES.forEach(function(vs){\n    sh += '<div class=row><span>' + vs.key",
          "  [{key:\"sow\"}].forEach(function(vs){\n    sh += '<div class=row><span>' + vs.key",
  "status_panel", "the status panel hard-coding one state"),
 ("tmpl", 'T.byView[inp.dataset.st] = T.byView[inp.dataset.st] || {};\n      T.byView[inp.dataset.st].main = inp.value;',
          'T.byView.sow = T.byView.sow || {};\n      T.byView.sow.main = inp.value;',
  "status_panel", "every status field writing through to one state"),
 # ---- the exports ------------------------------------------------------------------------------------------------------------
 ("tmpl", '      d[a.key] = {name: act.name, shortLabel: act.shortLabel};',
          '      d[a.key] = {name: act.name, shortLabel: act.shortLabel, scenic: act.scenic};',
  "game_layout", "an asset leaked into the game layout"),
 ("tmpl", "    city: {x: S.city.x, y: S.city.y, width: S.city.width, height: S.city.height,",
          "    city: clone(S.city) && {x: S.city.x, y: S.city.y, width: S.city.width, height: S.city.height, counts: S.city.counts,",
  "game_layout", "the City's session counts exported as layout"),
 ("tmpl", "             visible: !!S.status.visible, byView: msgs},",
          "             visible: !!S.status.visible},",
  "game_layout", "the instruction exported without its text"),
 ("tmpl", "            ratio: WHEEL_RATIO, ground: !!S.wheel.ground, opacity: S.wheel.opacity},",
          "            ground: !!S.wheel.ground, opacity: S.wheel.opacity},",
  "game_layout", "the wheel exported without its ratio"),
 # ---- migration -----------------------------------------------------------------------------------------------------------------
 ("tmpl", '      delete D.label;              // nothing identifies a duty space on the wheel in V4',
          '      ;',
  "older_layout_keeps or v1_layout", "the retired duty label kept alive through migration"),
 ("tmpl", '    ["wheel", "status", "city", "tithe"].forEach(function(k){',
          '    [].forEach(function(k){',
  "older_layout_keeps", "V3 band geometry carried across the V4 boundary"),
 ("tmpl", '''        main[vs.key] = {main: (old && old.main) || def.status.byView[vs.key].main};''',
          '''        main[vs.key] = {main: def.status.byView[vs.key].main};''',
  "older_layout_keeps", "an older file's instructions retyped on import"),
 ("tmpl", '      var keep = {count: d.inHand.count, seat: d.inHand.seat,',
          '      var keep = {count: def.inHand.count, seat: def.inHand.seat,',
  "older_layout_keeps", "the in-hand pool's count reset on import"),
 # ---- persistence and undo --------------------------------------------------------------------------------------------------------
 ("tmpl", 'function putImage(url){ var k = "im" + (++IMG_SEQ); IMAGES[k] = url; return k; }',
          'function putImage(url){ var k = "im" + (++IMG_SEQ); IMAGES[k] = url; return url; }',
  "autosave", "the image pool bypassed, bytes put straight into the state"),
 # ---- V4.2.1: lock semantics --------------------------------------------------------------------------------------------------
 ("tmpl", 'say("cannot " + needed.verb + " · "', 'say("cannot " + stuck.verb + " · "',
  "refuses_as_a_whole", "the verb read off the array the guard builds ('cannot undefined')"),
 ("tmpl", '        ? " are locked" : " is locked"), true);\n  return false;',
          '        ? " are locked" : " is locked"), true);\n  commit();\n  return false;',
  "refuses_as_a_whole", "a refusal leaving an undo entry behind"),
 ("tmpl", 'if (!requireUnlocked(needs("align the duty cards", ALL_CARDS()))) return;',
          'if (!requireUnlocked(needs("align the duty cards", ALL_CARDS().slice(1)))) return;',
  "refuses_as_a_whole", "align card tops ignoring the anchor card's own lock"),
 ("tmpl", '''  if (!requireUnlocked(needs("resize the action artwork",
                             [ART_L(), ART_R(), TITHE_O(), CITY_O()]))) return;
  var v = clamp(Math.round(w), HELPERS.artW[0], HELPERS.artW[1]);''',
          '''  if (!requireUnlocked(needs("resize the action artwork", [ART_L(), ART_R()]))) return;
  var v = clamp(Math.round(w), HELPERS.artW[0], HELPERS.artW[1]);''',
  "refuses_as_a_whole", "the linked width forgetting it re-lays Tithe and the City"),
 ("tmpl", '''  if (!requireUnlocked(needs("re-space the action row",
                             [ART_R(), TITHE_O(), CITY_O()]))) return;''',
          '''  if (!requireUnlocked(needs("re-space the action row",
                             [ART_L(), ART_R(), TITHE_O(), CITY_O()]))) return;''',
  "refuses_as_a_whole", "the row gap refusing over the anchor it never writes"),
 ("tmpl", '''function setWheelWidth(w, soon){
  if (!requireUnlocked(needs("resize the wheel", [WHEEL_O()]))) return;
  var W = S.wheel;''',
          '''function setWheelWidth(w, soon){
  var W = S.wheel;
  if (!requireUnlocked(needs("resize the wheel", [WHEEL_O()]))) return;''',
  "refuses_as_a_whole", "the wheel helper reading the object before it checks the lock"),
 ("tmpl", 'if (!requireUnlocked(needs("centre the wheel", [WHEEL_O()]))) return;',
          'if (lockedOf("wheel", null)) return;',
  "refuses_as_a_whole", "one helper checking the lock itself and refusing in silence"),
 # ---- V4.2.1: control synchronisation ------------------------------------------------------------------------------------------
 ("tmpl", '  paintMetrics();\n  syncHelperInputs();', '  paintMetrics();',
  "refreshed_from_render", "the controls never re-synced from render"),
 ("tmpl", '  paintMetrics();\n  syncHelperInputs();', '  syncHelperInputs();\n  paintMetrics();',
  "refreshed_from_render", "the controls synced before the metrics, so the two can disagree"),
 # ANCHORED ON THE LINE ABOVE IT. There are two of these now -- syncHelperInputs() and
 # syncTokenInputs() protect their controls the same way -- so the guard alone is ambiguous, and
 # a mutation that hit both would not say which one the failing test was about. This is exactly
 # the case replace_exactly_once() exists to refuse: `source.replace` would have changed both
 # and reported a clean result.
 ("tmpl", '    var e = el(id);\n    if (!e || e === document.activeElement) return;',
          '    var e = el(id);\n    if (!e) return;',
  "refreshed_from_render", "the helper refresh stamping on the box the caret is in"),
 ("tmpl", 'function syncHelperInputs(){\n  if (!el("hpWheelN")) return;',
          'function syncHelperInputs(){\n  if (!el("hpWheelN")) return;\n  panels();',
  "refreshed_from_render", "the refresh rebuilding the panel instead of writing into it"),
 ("tmpl", '  set("hpCardN", cg.h.lo);         set("hpCardR", cg.h.lo);',
          '  set("hpCardN", cg.h.hi);         set("hpCardR", cg.h.hi);',
  "refreshed_from_render", "the card control showing the tallest card, not the group value"),
 ("tmpl", 'function helperGap(){ return clamp(rowGapSuggested(), HELPERS.gap[0], HELPERS.gap[1]); }',
          'function helperGap(){ return rowGapSuggested(); }',
  "refreshed_from_render", "the gap control showing a value its own slider cannot reach"),
 ("tmpl", '      var actual = read();\n      r.value = actual;',
          '      var actual = v;\n      r.value = actual;',
  "refreshed_from_render", "the control echoing the typed number instead of the geometry"),
 # ---- V4.2.1: the fit is the only repair ---------------------------------------------------------------------------------------
 ("tmpl", '  var gap = clamp(raw, HELPERS.gap[0], HELPERS.gap[1]);',
          '  var gap = raw;',
  "only_the_repair_button", "a fit that rebuilds the row at the overlap it found"),
 ("tmpl", '      + (raw !== gap ? " · normalised from " + raw',
          '      + (true ? " · normalised from " + raw',
  "only_the_repair_button", "the fit claiming a normalisation it did not make"),
 ("tmpl", '''  var gap = rowGapSuggested();
  artOf("left").width = v; artOf("right").width = v;''',
          '''  var gap = clamp(rowGapSuggested(), HELPERS.gap[0], HELPERS.gap[1]);
  artOf("left").width = v; artOf("right").width = v;''',
  "only_the_repair_button", "the clamp spreading from the repair to the ordinary resize"),
 ("tmpl", '''  var gap = rowGapSuggested();
  artOf("left").width = v; artOf("right").width = v;
  layoutActionRow(gap);''',
          '''  artOf("left").width = v; artOf("right").width = v;
  layoutActionRow(rowGapSuggested());''',
  "only_the_repair_button", "the gap measured after the widths move (the V4.2 bug)"),
]

# THIS SUITE MUTATES THE PRODUCTION SOURCE IN PLACE and restores it after each test, so an
# interrupted run leaves the repository holding a deliberate bug. That is not hypothetical: a
# killed run left `check_design_ratio` sitting at `if False:` -- the 32 degree invariant switched
# off in the working tree -- and it was found only because the next run reported the target as
# stale. Restoring from an atexit hook covers the ordinary interrupt; the integrity check at the
# end covers the rest.
def _restore():
    if T.read_text() != TB:
        T.write_text(TB)
        print("  (restored the template after an interrupted run)")
    if G.read_text() != GB:
        G.write_text(GB)
        print("  (restored the generator after an interrupted run)")


atexit.register(_restore)
# atexit does not run on a bare SIGTERM, which is what a timed-out or cancelled run usually
# gets, so it is turned into an ordinary exit first.
for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(_sig, lambda n, frame: sys.exit("interrupted by signal %d" % n))

run = MutationRun("V4 source mutations vs the pytest suite", total=len(MUTS))
for where, old, new, k, label in MUTS:
    f, base = (T, TB) if where == "tmpl" else (G, GB)
    try:
        # A target written as "re:<pattern>" is matched as a regex. The version declaration uses
        # one deliberately: a literal marker for it is correct until the version moves, which is
        # the one moment it needs to be right -- this entry sat pinned at "4.2" for a whole
        # version, replacing nothing and testing nothing.
        mutated = (replace_regex_exactly_once(base, old[3:], new, label) if old.startswith("re:")
                   else replace_exactly_once(base, old, new, label))
    except MutationTargetError as err:
        # NOT a skip -- see mutation_tools.py. A stale target tests nothing and reds the run.
        run.record_invalid(label, err)
        continue
    f.write_text(mutated)
    # THE BYTECODE CACHE HAS TO GO. Several mutations are the same length as the text they
    # replace, so size and mtime are unchanged and CPython reuses the cached .pyc -- a real
    # failure then reads as a pass. That has happened twice on this file.
    shutil.rmtree(LAB / "__pycache__", ignore_errors=True)
    shutil.rmtree(TESTS / "__pycache__", ignore_errors=True)
    r = subprocess.run([sys.executable, "-m", "pytest",
                        str(TESTS / "test_board_v2_layout_lab.py"),
                        "-q", "-k", k, "-p", "no:cacheprovider"],
                       capture_output=True, text=True, cwd=str(ROOT))
    f.write_text(base)
    lines = [ln for ln in r.stdout.splitlines()
             if "passed" in ln or "failed" in ln or "error" in ln]
    last = lines[-1] if lines else r.stdout[-160:]
    # A -k that selects NOTHING reports "no tests ran", which is not a catch and not a pass --
    # it means the selector has gone stale the same way a marker does.
    if "no tests ran" in last or " 0 selected" in last:
        run.record_invalid(label, "the -k selector %r matched no tests" % k)
        continue
    run.record(label, "failed" in last or "error" in last, last)

shutil.rmtree(LAB / "__pycache__", ignore_errors=True)

# AND PROVE THE SOURCE CAME BACK. A suite that leaves the production files mutated has done
# something far worse than fail.
_intact = True
for f, base, name in ((T, TB, "the template"), (G, GB, "the generator")):
    if f.read_text() != base:
        print("\n** %s was NOT restored to its original bytes" % name)
        f.write_text(base)
        _intact = False
if not _intact:
    print("** the sources have been put back, but this run is red regardless")

raise SystemExit(run.report() or (0 if _intact else 1))
