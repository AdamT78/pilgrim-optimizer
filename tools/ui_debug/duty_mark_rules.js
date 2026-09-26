// HOW A MARKED TILE IS LIT. This file is THE copy.
//
// Inlined verbatim into every page that draws a marked tile -- the placement sheet, where you
// choose the marking, and the sow, where you play on it. Same reason duty_sculpt_rules.js
// exists: the amber was written once in the sheet as a prototype, and the moment the sow had to
// draw it too there were going to be two answers to one question, each looking correct alone.
//
// Numbers come from ui/assets-gothic/metadata/duty_effects.json. Nothing here decides what an
// effect looks like -- this is the TECHNIQUE, the file is the COLOUR.
//
// THE POINT OF ALL OF IT is that adding an effect is a change to that file and nothing else. No
// function below knows the name "amber", and none of them should learn it: a branch on one
// effect's name is the catalogue quietly turning back into a switch statement with a dropdown
// in front of it. If an effect needs behaviour the others do not have, the behaviour belongs
// here, driven by a key in the entry, so that both pages get it at once.

// ---- naming ---------------------------------------------------------------------------------
// `mark` in duty_placement.json answers one question -- how is a live tile marked -- and its
// answer is either one of the floor styles the sow draws in geometry (floor, foot, box, gild)
// or the name of an effect in the catalogue. One key, because the two are alternatives: the
// amber REPLACES the floor line rather than joining it, and two keys would have let both be set
// with nothing to say which wins.
//
// An effect name may carry the modifier `:pulse`, as in `amber:pulse`. A colon reads as "the
// same thing, breathing" rather than as a second effect, which is what it is -- the solid and
// the pulsing marking are one entry in the catalogue so that their colour cannot drift apart.
// Effect names are [a-z][a-z0-9_]* and so can never contain the colon themselves.
function dutyMarkParse(mark) {
  var s = String(mark == null ? "" : mark);
  var at = s.indexOf(":");
  if (at < 0) return {name: s, pulse: false};
  return {name: s.slice(0, at), pulse: s.slice(at + 1) === "pulse"};
}

// The catalogue entry a mark names, or null when it names a floor style -- or nothing the
// catalogue holds, which the loader refuses long before a page gets here. Pages ask this rather
// than comparing against a list of names they carry, so a page never needs to know what is in
// the file.
function dutyEffectFor(effects, mark) {
  var want = dutyMarkParse(mark);
  var fx = ((effects || {}).effects || effects || {})[want.name];
  return fx && typeof fx === "object" ? fx : null;
}

// Whether this mark asks for the breathing version, which is only honest if the entry has the
// numbers to breathe with. The loader refuses `x:pulse` where x has no pulse block, so this is
// belt and braces rather than the guard.
function dutyMarkPulses(effects, mark) {
  var fx = dutyEffectFor(effects, mark);
  return !!(fx && fx.pulse && dutyMarkParse(mark).pulse);
}

// ---- one entry, as CSS ------------------------------------------------------------------------
// Every number the marking is drawn with, as custom properties on the layer itself. This is the
// whole of what an effect IS as far as the drawing is concerned, which is why a new entry needs
// no new CSS: the rules below are written against the properties, not against any effect.
function dutyEffectVars(fx) {
  if (!fx) return "";
  var p = fx.pulse || {};
  return "--mkc:hsl(" + (fx.hue || 0) + " " + (fx.saturation || 0) + "% "
       + (fx.lightness || 0) + "%)"
       + ";--mks:" + ((fx.strength || 0) / 100)
       + ";--mklo:" + ((p.lo || 0) / 100)
       + ";--mkhi:" + ((p.hi || 0) / 100)
       + ";--mksp:" + (p.speed || 0) + "ms";
}

// The rules the layer is drawn by, once, for whatever effect is on it.
//
// `scope` is what has to be true for the marking to SHOW, and is the one thing the two pages
// disagree about: in the sow a tile is marked only while something is in hand, so the caller
// passes ".cell.live "; the sheet shows the marking on all nine so you can judge it, and passes
// "". Everything else -- and in particular the blend group -- is identical on both, which is
// the reason it lives here.
//
// THE FLOOD AND THE PLATE MUST SHARE AN ISOLATION GROUP. mix-blend-mode blends with its
// backdrop, and a backdrop outside the group is not one: with the animated opacity on the layer
// above, every blend mode measured identical RGB on 2026-09-25, which is what nothing-blending
// looks like from the outside. `.mkblend` is that group and is not decoration.
function dutyEffectCss(scope) {
  var s = scope || "";
  return [
    ".mkfx{position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .14s}",
    s + ".mkfx{opacity:var(--mks)}",
    s + ".mkfx.mk-pulse{animation:mkpulse var(--mksp) ease-in-out infinite}",
    "@keyframes mkpulse{0%,100%{opacity:var(--mklo)}50%{opacity:var(--mkhi)}}",
    ".mkblend{position:absolute;inset:0;isolation:isolate}",
    ".mkblend img{position:absolute;inset:0;width:100%;height:100%}",
    ".mkflood{position:absolute;inset:0;background:var(--mkc);mix-blend-mode:color;",
    "  -webkit-mask-image:var(--plate);mask-image:var(--plate);",
    "  -webkit-mask-size:100% 100%;mask-size:100% 100%;",
    "  -webkit-mask-repeat:no-repeat;mask-repeat:no-repeat}"
  ].join("\n");
}

// ---- the plate, marked or not -----------------------------------------------------------------
// BOTH PAGES EMIT THIS, which they did not before: the sow put brightness and saturation
// straight on the plate's wrapper and the sheet had moved them onto the <img> so the amber
// would not be desaturated along with the stone. The pages drew the same plate two ways and
// only one of them could carry a marking.
//
// `box` is {left, top, w, h} in real device pixels. `transp` is duty_grounds.json's one
// transparency, 0-100, 0 being solid; it is applied to the WRAPPER, so the marking fades with
// the ground rather than floating over a ground that is not there.
function dutyPlateHtml(plate, gs, box, transp, fx, pulsing) {
  if (!plate) return "";
  function px(v) { return Math.round(v * 100) / 100 + "px"; }
  var fil = "filter:brightness(" + (gs.dim / 100) + ") saturate(" + (gs.saturate / 100) + ")";
  var uri = plate.uri;
  var h = '<div class=plate style="left:' + px(box.left) + ';top:' + px(box.top)
        + ';width:' + px(box.w) + ';height:' + px(box.h)
        + ';opacity:' + ((100 - (transp || 0)) / 100) + '">'
        + '<img style="' + fil + '" src="' + uri + '">';
  if (fx) {
    // A SECOND COPY OF THE PLATE, stacked on the resting one, and only this copy's opacity
    // moves. Tint the single copy instead and the pulse takes the acolytes standing on it with
    // it, which reads as the figures breathing rather than the ground.
    h += '<div class="mkfx' + (pulsing ? " mk-pulse" : "") + '" style="'
       + dutyEffectVars(fx) + ';--plate:url(&quot;' + uri + '&quot;)">'
       + '<div class=mkblend><img style="' + fil + '" src="' + uri + '">'
       + '<div class=mkflood></div></div></div>';
  }
  return h + "</div>";
}
